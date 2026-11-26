"""Piper text-to-speech behind an OpenAI-style API, used for voices Kokoro does not have (Albanian by default).

Voices are listed in PIPER_VOICES as  name=URL-of-model.onnx  pairs, separated by commas.
The matching .onnx.json config is fetched from the same URL + ".json". Models are downloaded once into MODELS_DIR.
"""
from __future__ import annotations

import io
import os
import subprocess
import threading
import wave
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

DEFAULT_VOICES = "sq_arben=https://huggingface.co/edonseki/folsh.ai/resolve/main/arben/sq_AL-arben-medium.onnx,sq_arta=https://huggingface.co/edonseki/folsh.ai/resolve/main/arta/sq_AL-arta-medium.onnx,sq_dren=https://huggingface.co/edonseki/folsh.ai/resolve/main/dren/sq_AL-dren-medium.onnx,sq_edon=https://huggingface.co/edonseki/folsh.ai/resolve/main/edon/sq_AL-edon-medium.onnx"
MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/models"))
MEDIA = {"mp3": "audio/mpeg", "wav": "audio/wav"}


def parse_voices(spec: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in spec.split(","):
        if "=" in item:
            name, url = item.split("=", 1)
            if name.strip() and url.strip():
                out[name.strip()] = url.strip()
    return out


class Voices:
    """Downloads and loads voices in the background so the API answers right away."""

    def __init__(self, spec: dict[str, str]):
        self.spec = spec
        self.loaded: dict[str, object] = {}
        self.errors: dict[str, str] = {}
        self.lock = threading.Lock()
        self.synth_lock = threading.Lock()  # one synthesis at a time keeps memory flat

    def start(self) -> None:
        threading.Thread(target=self._load_all, daemon=True).start()

    def _download(self, url: str, dest: Path) -> None:
        if dest.exists() and dest.stat().st_size > 0:
            return
        tmp = dest.with_suffix(dest.suffix + ".part")
        with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(600, connect=20)) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        os.replace(tmp, dest)

    def _load_all(self) -> None:
        from piper import PiperVoice  # imported here so tests can run without the model

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in self.spec.items():
            try:
                model = MODELS_DIR / f"{name}.onnx"
                config = MODELS_DIR / f"{name}.onnx.json"
                self._download(url, model)
                self._download(url + ".json", config)
                voice = PiperVoice.load(model, config_path=config)
                with self.lock:
                    self.loaded[name] = voice
                    self.errors.pop(name, None)
            except Exception as exc:  # keep going with the other voices
                msg = f"{type(exc).__name__}: {exc}"[:300]
                print(f"[piper] voice {name} failed: {msg}", flush=True)
                with self.lock:
                    self.errors[name] = msg
                continue
            print(f"[piper] voice {name} ready", flush=True)

    def ready(self) -> bool:
        with self.lock:
            return bool(self.loaded)

    def wav(self, name: str, text: str, speed: float) -> bytes:
        from piper import SynthesisConfig

        with self.lock:
            voice = self.loaded.get(name)
        if voice is None:
            raise KeyError(name)
        buf = io.BytesIO()
        with self.synth_lock, wave.open(buf, "wb") as wf:
            voice.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=1.0 / max(0.5, min(2.0, speed))))
        return buf.getvalue()


voices = Voices(parse_voices(os.environ.get("PIPER_VOICES", DEFAULT_VOICES)))
app = FastAPI(title="Piper TTS (OpenAI-compatible)")


@app.on_event("startup")
def _startup() -> None:
    voices.start()


@app.get("/live", include_in_schema=False)
def live():
    return {"ok": True}


@app.get("/health")
def health():
    with voices.lock:
        body = {"status": "ready" if voices.loaded else "loading", "voices": sorted(voices.loaded), "errors": dict(voices.errors)}
    if not body["voices"]:
        return Response(content=__import__("json").dumps(body), status_code=503, media_type="application/json")
    return body


@app.get("/v1/audio/voices")
def list_voices():
    with voices.lock:
        return {"voices": sorted(voices.loaded)}


class SpeechRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20000)
    voice: str
    model: str | None = None
    speed: float = 1.0
    response_format: str = "mp3"


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if req.response_format not in MEDIA:
        raise HTTPException(400, "response_format must be mp3 or wav")
    if not voices.ready():
        raise HTTPException(503, "Voices are still downloading. Try again in a minute.")
    try:
        audio = voices.wav(req.voice, req.input, req.speed)
    except KeyError:
        raise HTTPException(400, f"Unknown voice '{req.voice}'. Available: {', '.join(sorted(voices.loaded))}")
    if req.response_format == "mp3":
        audio = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "wav", "-i", "-", "-codec:a", "libmp3lame", "-q:a", "3", "-f", "mp3", "-"],
            input=audio, capture_output=True, check=True,
        ).stdout
    return Response(audio, media_type=MEDIA[req.response_format])
