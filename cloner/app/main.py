"""Voice cloning with Qwen3-TTS (Apache 2.0), behind the same OpenAI-style API as the other voice engines.

- POST /voices        upload a short reference clip (multipart: name, consent=true, file, optional start and transcript)
                      -> new voice "clone_<slug>". The transcript (what is said in the clip) gives a much closer copy.
- GET  /voices        list saved voices with details
- DELETE /voices/{id} delete a voice and its clip
- GET  /v1/audio/voices, POST /v1/audio/speech   used by Narrated Slides like any other engine

The model is downloaded once into HF_HOME on first start and loaded in the background.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

VOICES_DIR = Path(os.environ.get("VOICES_DIR", "/voices"))
DEVICE = os.environ.get("CLONE_DEVICE", "cpu")  # mps on Apple Silicon (scripts/run-cloner-mac.sh), cuda with an NVIDIA GPU
QWEN_MODEL = os.environ.get("QWEN_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
QWEN_LANGUAGE = os.environ.get("QWEN_LANGUAGE", "English")
MAX_CLIP = 20.0  # seconds kept from an upload
# How much the delivery may vary from sentence to sentence. The emotion itself comes from the reference recording
# (the model copies its tone); these sampling settings decide how freely it plays with it.
STYLES = {
    "steady": {"temperature": 0.6, "top_p": 0.8},
    "natural": {},  # the model's own defaults
    "expressive": {"temperature": 1.05, "top_p": 0.95},
}
MAX_UPLOAD = 100 * 1024 * 1024  # videos (e.g. a saved reel) are fine: only the audio is kept
MEDIA = {"mp3": "audio/mpeg", "wav": "audio/wav"}


class Engine:
    kind = "qwen"

    def __init__(self) -> None:
        self.model = None
        self.sr = 24000
        self.error: str | None = None
        self.lock = threading.Lock()
        self.prompts: dict[tuple[str, float], object] = {}  # analysed reference clips, reused across sentences

    def start(self) -> None:
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            import torch
            from qwen_tts import Qwen3TTSModel

            torch.set_num_threads(max(1, os.cpu_count() or 4))
            # bfloat16 on NVIDIA; float32 elsewhere (half precision makes the clone model produce NaNs on the Mac GPU)
            dtype = torch.bfloat16 if DEVICE.startswith("cuda") else torch.float32
            print(f"[cloner] loading Qwen3-TTS {QWEN_MODEL} on {DEVICE} (first start downloads the model)…", flush=True)
            self.model = Qwen3TTSModel.from_pretrained(QWEN_MODEL, device_map=DEVICE, dtype=dtype)
            print(f"[cloner] model ready (qwen, {DEVICE})", flush=True)
            for meta in voice_meta():  # analyse saved voices now, so the first preview doesn't wait
                self.warm(VOICES_DIR / f"{meta['id']}.wav")
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"[:400]
            print(f"[cloner] model failed to load: {self.error}", flush=True)

    def _prompt(self, ref: Path):
        """Build the voice prompt once per clip (call with self.lock held)."""
        key = (str(ref), ref.stat().st_mtime)
        if key not in self.prompts:
            transcript = (voice_info(ref.stem).get("transcript") or "").strip()
            if transcript:
                prompt = self.model.create_voice_clone_prompt(ref_audio=str(ref), ref_text=transcript)
            else:  # without the words, only the speaker's timbre is used
                prompt = self.model.create_voice_clone_prompt(ref_audio=str(ref), x_vector_only_mode=True)
            self.prompts[key] = prompt
        return self.prompts[key]

    def _say(self, chunk: str, prompt, style: str = "natural"):
        import numpy as np

        try:
            wavs, sr = self.model.generate_voice_clone(text=chunk, language=QWEN_LANGUAGE, voice_clone_prompt=prompt,
                                                       **STYLES.get(style, {}))
        except RuntimeError as exc:
            if "probability tensor" not in str(exc):
                raise
            # sampling broke (NaN); greedy decoding still gives good speech
            wavs, sr = self.model.generate_voice_clone(text=chunk, language=QWEN_LANGUAGE, voice_clone_prompt=prompt,
                                                       do_sample=False)
        self.sr = sr
        return tidy(wavs[0], sr)

    def warm(self, ref: Path) -> None:
        if self.model is None or not ref.exists():
            return
        try:
            with self.lock:
                self._prompt(ref)
        except Exception as exc:
            print(f"[cloner] could not prepare {ref.name}: {exc}", flush=True)

    def forget(self, voice_id: str) -> None:
        self.prompts = {k: v for k, v in self.prompts.items() if not k[0].endswith(f"/{voice_id}.wav")}

    def wav(self, text: str, ref: Path, style: str = "natural") -> bytes:
        """Generate sentence by sentence (long inputs make the model drift) and join as 16-bit WAV."""
        import numpy as np

        pieces = []
        with self.lock:
            prompt = self._prompt(ref)
            for chunk in split_text(text):
                pieces.append(self._say(chunk, prompt, style))
                pieces.append(np.zeros(int(self.sr * 0.25), dtype=np.float32))
        audio = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sr)
            wf.writeframes(pcm)
        return buf.getvalue()


def tidy(audio, sr: int, keep_head: float = 0.05, keep_tail: float = 0.12, max_gap: float = 0.6):
    """Cut the silence Qwen3-TTS sometimes leaves before/after a sentence (it can run for seconds and makes the video
    feel stuck) and shorten very long pauses inside it."""
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    hop = max(1, int(sr * 0.01))
    n = len(audio) // hop
    if n == 0:
        return audio
    rms = np.sqrt((audio[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    loud = rms > max(float(rms.max()) * 0.02, 1e-4)  # about -34 dB below the loudest part
    if not loud.any():
        return audio[:0]
    first, last = int(np.argmax(loud)), n - 1 - int(np.argmax(loud[::-1]))
    start = max(0, first * hop - int(sr * keep_head))
    end = min(len(audio), (last + 1) * hop + int(sr * keep_tail))
    # shorten long quiet stretches inside the sentence
    keep, run_start, gap = [], None, int(max_gap / 0.01)
    for i in range(first, last + 1):
        if not loud[i]:
            run_start = i if run_start is None else run_start
            continue
        if run_start is not None and i - run_start > gap:
            keep.append((run_start + gap // 2, i - gap // 2))  # frames to drop
        run_start = None
    if not keep:
        return audio[start:end]
    pieces, pos = [], start
    for a, b in keep:
        pieces.append(audio[pos:a * hop])
        pos = b * hop
    pieces.append(audio[pos:end])
    return np.concatenate(pieces)


def split_text(text: str, limit: int = 280) -> list[str]:
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        while len(sentence) > limit:
            cut = sentence.rfind(", ", 0, limit)
            cut = cut if cut > limit // 2 else sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            out.append(sentence[: cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if sentence.strip():
            out.append(sentence.strip())
    return out


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30]
    return slug or "voice"


def voice_meta() -> list[dict]:
    items = []
    for meta in sorted(VOICES_DIR.glob("*.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (VOICES_DIR / f"{data.get('id')}.wav").exists():
            items.append(data)
    return items


def voice_info(voice_id: str) -> dict:
    try:
        return json.loads((VOICES_DIR / f"{voice_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def public(meta: dict) -> dict:
    out = {k: v for k, v in meta.items() if k != "transcript"}
    out["has_transcript"] = bool(meta.get("transcript"))
    return out


def has_audio(path: str) -> bool:
    proc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                           "-of", "csv=p=0", path], capture_output=True, text=True)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def ffmpeg(args: list[str], data: bytes | None = None) -> bytes:
    proc = subprocess.run(["ffmpeg", "-loglevel", "error", *args], input=data, capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(400, "Could not read that file. Try an MP4/MOV video or a WAV, MP3, M4A or WebM recording.")
    return proc.stdout


engine = Engine()
app = FastAPI(title="Voice cloning (Qwen3-TTS, OpenAI-compatible)")


@app.on_event("startup")
def _startup() -> None:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    engine.start()


@app.get("/live", include_in_schema=False)
def live():
    return {"ok": True}


@app.get("/health")
def health():
    body = {"status": "ready" if engine.model else ("error" if engine.error else "loading"),
            "error": engine.error, "voices": len(voice_meta()), "model": engine.kind,
            "transcript": True, "styles": list(STYLES)}
    return body if engine.model else JSONResponse(body, status_code=503)


@app.get("/voices")
def list_my_voices():
    return {"voices": [public(m) for m in voice_meta()]}


@app.post("/voices")
async def add_voice(name: str = Form(..., min_length=1, max_length=40), consent: bool = Form(False),
                    file: UploadFile = File(...), start: float = Form(0.0, ge=0, le=3600),
                    transcript: str = Form("", max_length=1000)):
    if not consent:
        raise HTTPException(400, "Please confirm this is your voice or that you have permission to use it.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "The file is too large (100 MB max). Trim the video first.")
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "clip").suffix or ".bin") as src:
        src.write(data)
        src.flush()
        if not has_audio(src.name):
            raise HTTPException(400, "This file has no sound. Screen recordings on a Mac don't capture the computer's audio. "
                                     "Use Record to read the text aloud, or upload a video that has your voice in it.")
        # mono 24 kHz, silence trimmed at the start, at most 20 seconds
        wav = ffmpeg(["-ss", f"{start:.2f}", "-i", src.name, "-vn", "-af",
                      "silenceremove=start_periods=1:start_threshold=-45dB,highpass=f=70,afftdn=nf=-25,"
                      "loudnorm=I=-20:TP=-2:LRA=11",
                      "-ac", "1", "-ar", "24000", "-t", f"{MAX_CLIP:g}", "-f", "wav", "-"])
    seconds = (len(wav) - 44) / (24000 * 2)
    if seconds < 4:
        raise HTTPException(400, f"The recording is too short ({seconds:.1f} s). Record at least 5 seconds of clear speech.")
    base, n = "clone_" + slugify(name), 1
    vid = base
    while (VOICES_DIR / f"{vid}.wav").exists():
        n += 1
        vid = f"{base}_{n}"
    (VOICES_DIR / f"{vid}.wav").write_bytes(wav)
    meta = {"id": vid, "name": name.strip(), "seconds": round(seconds, 1), "created": time.time()}
    transcript = " ".join(transcript.split())
    if transcript and seconds < MAX_CLIP - 0.5:  # a clip cut at 20 s no longer matches its transcript
        meta["transcript"] = transcript
    (VOICES_DIR / f"{vid}.json").write_text(json.dumps(meta), encoding="utf-8")
    threading.Thread(target=engine.warm, args=(VOICES_DIR / f"{vid}.wav",), daemon=True).start()
    return public(meta)


@app.delete("/voices/{voice_id}")
def delete_voice(voice_id: str):
    if not re.fullmatch(r"clone_[a-z0-9_]+", voice_id) or not (VOICES_DIR / f"{voice_id}.wav").exists():
        raise HTTPException(404, "Unknown voice.")
    for ext in (".wav", ".json"):
        (VOICES_DIR / f"{voice_id}{ext}").unlink(missing_ok=True)
    engine.forget(voice_id)
    return {"ok": True}


@app.get("/v1/audio/voices")
def openai_voices():
    return {"voices": [v["id"] for v in voice_meta()]}


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20000)
    voice: str
    model: str | None = None
    speed: float = 1.0
    response_format: str = "mp3"
    style: str = Field("natural", pattern="^(steady|natural|expressive)$")  # Delivery


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if req.response_format not in MEDIA:
        raise HTTPException(400, "response_format must be mp3 or wav")
    ref = VOICES_DIR / f"{req.voice}.wav"
    if not re.fullmatch(r"clone_[a-z0-9_]+", req.voice) or not ref.exists():
        raise HTTPException(400, f"Unknown voice '{req.voice}'.")
    if engine.model is None:
        raise HTTPException(503, engine.error or "The voice-cloning model is still loading. Try again in a minute.")
    audio = engine.wav(req.input, ref, req.style)
    speed = max(0.5, min(2.0, req.speed))
    filters = [] if abs(speed - 1.0) < 0.01 else ["-af", f"atempo={speed}"]
    if req.response_format == "mp3":
        return Response(ffmpeg(["-f", "wav", "-i", "-", *filters, "-codec:a", "libmp3lame", "-q:a", "3", "-f", "mp3", "-"], audio),
                        media_type="audio/mpeg")
    if filters:
        audio = ffmpeg(["-f", "wav", "-i", "-", *filters, "-f", "wav", "-"], audio)
    return Response(audio, media_type="audio/wav")
