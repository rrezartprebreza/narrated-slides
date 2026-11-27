"""Voice cloning with Chatterbox (English), behind the same OpenAI-style API as the other voice engines.

- POST /voices        upload a short reference clip (multipart: name, consent=true, file) -> new voice "clone_<slug>"
- GET  /voices        list saved voices with details
- DELETE /voices/{id} delete a voice and its clip
- GET  /v1/audio/voices, POST /v1/audio/speech   used by Narrated Slides like any other engine

The model (~2 GB) is downloaded once into HF_HOME on first start and loaded in the background.
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
DEVICE = os.environ.get("CLONE_DEVICE", "cpu")
# turbo: much faster, no emotion control. standard: slower, supports the Emotion setting.
MODEL_KIND = os.environ.get("CLONE_MODEL", "turbo").strip().lower()
if MODEL_KIND not in ("turbo", "standard"):
    MODEL_KIND = "turbo"
MAX_UPLOAD = 100 * 1024 * 1024  # videos (e.g. a saved reel) are fine: only the audio is kept
MEDIA = {"mp3": "audio/mpeg", "wav": "audio/wav"}


class Engine:
    def __init__(self) -> None:
        self.model = None
        self.kind = MODEL_KIND
        self.error: str | None = None
        self.lock = threading.Lock()
        self.conds: dict[tuple[str, float], object] = {}  # analysed reference clips, reused across sentences

    def start(self) -> None:
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        try:
            import torch

            torch.set_num_threads(max(1, os.cpu_count() or 4))
            if self.kind == "turbo":
                from chatterbox.tts_turbo import ChatterboxTurboTTS as Model
            else:
                from chatterbox.tts import ChatterboxTTS as Model

            print(f"[cloner] loading Chatterbox {self.kind} (first start downloads the model)…", flush=True)
            self.model = Model.from_pretrained(device=DEVICE)
            print(f"[cloner] model ready ({self.kind}, {torch.get_num_threads()} CPU threads)", flush=True)
            for meta in voice_meta():  # analyse saved voices now, so the first preview doesn't wait
                self.warm(VOICES_DIR / f"{meta['id']}.wav")
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"[:400]
            print(f"[cloner] model failed to load: {self.error}", flush=True)

    def _prepare(self, ref: Path, exaggeration: float = 0.5) -> None:
        """Analyse a reference clip once and keep the result (call with self.lock held)."""
        key = (str(ref), ref.stat().st_mtime)
        if key not in self.conds:
            if self.kind == "turbo":
                self.model.prepare_conditionals(str(ref))
            else:
                self.model.prepare_conditionals(str(ref), exaggeration=exaggeration)
            self.conds[key] = self.model.conds
        self.model.conds = self.conds[key]

    def warm(self, ref: Path) -> None:
        if self.model is None or not ref.exists():
            return
        try:
            with self.lock:
                self._prepare(ref)
        except Exception as exc:
            print(f"[cloner] could not prepare {ref.name}: {exc}", flush=True)

    def wav(self, text: str, ref: Path, exaggeration: float = 0.5, cfg_weight: float = 0.5) -> bytes:
        """Generate sentence by sentence (long inputs make the model drift) and join as 16-bit WAV."""
        import numpy as np

        chunks = split_text(text)
        pieces = []
        with self.lock:
            # Analysing the reference clip is slow: do it once per voice (and file version), not per sentence.
            self._prepare(ref, exaggeration)
            for chunk in chunks:
                if self.kind == "turbo":
                    out = self.model.generate(chunk)
                else:
                    out = self.model.generate(chunk, exaggeration=exaggeration, cfg_weight=cfg_weight)
                pieces.append(out.squeeze().detach().cpu().numpy())
                pieces.append(np.zeros(int(self.model.sr * 0.25), dtype=np.float32))
        audio = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.model.sr)
            wf.writeframes(pcm)
        return buf.getvalue()


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
app = FastAPI(title="Voice cloning (Chatterbox, OpenAI-compatible)")


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
            "emotion": engine.kind == "standard"}
    return body if engine.model else JSONResponse(body, status_code=503)


@app.get("/voices")
def list_my_voices():
    return {"voices": voice_meta()}


@app.post("/voices")
async def add_voice(name: str = Form(..., min_length=1, max_length=40), consent: bool = Form(False),
                    file: UploadFile = File(...), start: float = Form(0.0, ge=0, le=3600)):
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
                      "-ac", "1", "-ar", "24000", "-t", "20", "-f", "wav", "-"])
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
    (VOICES_DIR / f"{vid}.json").write_text(json.dumps(meta), encoding="utf-8")
    threading.Thread(target=engine.warm, args=(VOICES_DIR / f"{vid}.wav",), daemon=True).start()
    return meta


@app.delete("/voices/{voice_id}")
def delete_voice(voice_id: str):
    if not re.fullmatch(r"clone_[a-z0-9_]+", voice_id) or not (VOICES_DIR / f"{voice_id}.wav").exists():
        raise HTTPException(404, "Unknown voice.")
    for ext in (".wav", ".json"):
        (VOICES_DIR / f"{voice_id}{ext}").unlink(missing_ok=True)
    engine.conds = {k: v for k, v in engine.conds.items() if not k[0].endswith(f"/{voice_id}.wav")}
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
    exaggeration: float = Field(0.5, ge=0.25, le=2.0)  # emotion: 0.3 calm ... 1.2+ dramatic
    cfg_weight: float = Field(0.5, ge=0.0, le=1.0)


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if req.response_format not in MEDIA:
        raise HTTPException(400, "response_format must be mp3 or wav")
    ref = VOICES_DIR / f"{req.voice}.wav"
    if not re.fullmatch(r"clone_[a-z0-9_]+", req.voice) or not ref.exists():
        raise HTTPException(400, f"Unknown voice '{req.voice}'.")
    if engine.model is None:
        raise HTTPException(503, engine.error or "The voice-cloning model is still loading. Try again in a minute.")
    audio = engine.wav(req.input, ref, req.exaggeration, req.cfg_weight)
    speed = max(0.5, min(2.0, req.speed))
    filters = [] if abs(speed - 1.0) < 0.01 else ["-af", f"atempo={speed}"]
    if req.response_format == "mp3":
        return Response(ffmpeg(["-f", "wav", "-i", "-", *filters, "-codec:a", "libmp3lame", "-q:a", "3", "-f", "mp3", "-"], audio),
                        media_type="audio/mpeg")
    if filters:
        audio = ffmpeg(["-f", "wav", "-i", "-", *filters, "-f", "wav", "-"], audio)
    return Response(audio, media_type="audio/wav")
