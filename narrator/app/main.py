"""HTTP API + static UI for the narrated-slides app."""
from __future__ import annotations

import shutil
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, llm, pipeline, presenton, store, tts, video
from .jobs import manager

STATIC = Path(__file__).parent / "static"
SAMPLE_DECK = Path(__file__).parent / "assets" / "sample-deck.pptx"
MAX_NOTE_CHARS = 6000


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.root()
    store.cleanup_old()
    yield


app = FastAPI(title="Narrated Slides", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------- models ----------

class PreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    voice: str | None = None
    speed: float = Field(1.0, ge=0.5, le=2.0)
    style: Literal["steady", "natural", "expressive"] = "natural"


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=8000)
    n_slides: int | None = Field(None, ge=1, le=50)
    tone: Literal["default", "casual", "professional", "funny", "educational", "sales_pitch"] = "default"
    verbosity: Literal["concise", "standard", "text-heavy"] = "standard"
    template: str = Field("general", max_length=80)


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class NotesRequest(BaseModel):
    notes: dict[str, str] = {}


class SuggestRequest(BaseModel):
    notes: dict[str, str] = {}  # current text in the UI, so filled slides are left alone
    slides: list[int] | None = None  # explicit slide numbers; None = every empty slide
    sentences: int = Field(3, ge=1, le=8)
    language: str | None = Field(None, max_length=40)  # e.g. "Albanian"; None = same language as the slide


class RenderRequest(BaseModel):
    notes: dict[str, str] = {}
    voice: str | None = None
    speed: float = Field(1.0, ge=0.5, le=2.0)
    style: Literal["steady", "natural", "expressive"] = "natural"
    pause: float = Field(0.8, ge=0, le=5)
    silent_seconds: float = Field(3.0, ge=0.5, le=30)
    resolution: Literal[720, 1080] = 1080
    subtitle_languages: list[Literal["en", "sq", "it", "pt", "no", "tr"]] = Field(default_factory=list, max_length=6)


def _check_notes(notes: dict[str, str]) -> dict[str, str]:
    for key, value in notes.items():
        if not key.isdigit():
            raise HTTPException(400, "Notes must be keyed by slide number.")
        if len(value) > MAX_NOTE_CHARS:
            raise HTTPException(400, f"Notes for slide {key} are longer than {MAX_NOTE_CHARS} characters.")
    return notes


def _deck_or_404(deck_id: str) -> dict:
    try:
        return store.load(deck_id)
    except store.DeckNotFound:
        raise HTTPException(404, "Deck not found (it may have been cleaned up). Upload it again.")


# ---------- pages & health ----------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/sample-deck.pptx", include_in_schema=False)
def sample_download():
    return FileResponse(SAMPLE_DECK, filename="narrated-slides-sample.pptx")


@app.get("/api/live", include_in_schema=False)
def live():
    return {"ok": True}


@app.get("/api/health")
def health():
    return {
        "version": __version__,
        "tts": tts.healthy(),
        "extra_tts": tts.extra_healthy(),
        "clone": tts.clone_healthy(),
        "clone_model": tts.clone_model(),
        "clone_native": "host.docker.internal" in config.CLONE_TTS_URL,
        "default_voice": config.TTS_VOICE,
        "llm_configured": llm.configured(),
        "llm": llm.healthy(),
        "presenton": presenton.healthy(),
        "presenton_api_key": bool(config.PRESENTON_API_KEY),
        "presenton_url": config.PRESENTON_PUBLIC_URL,
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


@app.get("/api/voices")
def get_voices():
    return {"voices": tts.voices(), "default": config.TTS_VOICE}


@app.post("/api/tts/preview")
def tts_preview(req: PreviewRequest):
    try:
        audio = tts.speech(req.text, req.voice, req.speed, "mp3", req.style)
    except tts.TTSError as exc:
        raise HTTPException(502, str(exc))
    return Response(audio, media_type="audio/mpeg")


# ---------- decks ----------

@app.post("/api/decks")
async def upload_deck(file: UploadFile):
    filename = Path(file.filename or "deck.pptx").name
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(400, "Please upload a .pptx file. Save .ppt or Keynote decks as PPTX first.")
    deck_id, d = store.new_deck()
    target = d / "source.pptx"
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with open(target, "wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                fh.close()
                store.discard(deck_id)
                raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB.")
            fh.write(chunk)
    if not zipfile.is_zipfile(target):
        store.discard(deck_id)
        raise HTTPException(400, "That file is not a valid .pptx.")
    name = Path(filename).stem
    job = manager.submit("prepare", lambda j: pipeline.prepare_deck(deck_id, j, name))
    return {"job_id": job.id, "deck_id": deck_id}


@app.post("/api/decks/sample")
def sample_deck():
    """Create a deck from the bundled 5-slide sample so newcomers can try the app in one click."""
    deck_id, d = store.new_deck()
    shutil.copyfile(SAMPLE_DECK, d / "source.pptx")
    job = manager.submit("prepare", lambda j: pipeline.prepare_deck(deck_id, j, "Sample deck"))
    return {"job_id": job.id, "deck_id": deck_id}


@app.get("/api/decks")
def list_decks():
    return {"decks": store.list_decks()}


@app.post("/api/decks/generate")
def generate_deck(req: GenerateRequest):
    deck_id, _ = store.new_deck()
    job = manager.submit("generate", lambda j: pipeline.generate_deck(deck_id, j, req.model_dump()))
    return {"job_id": job.id, "deck_id": deck_id}


@app.get("/api/decks/{deck_id}")
def get_deck(deck_id: str):
    return _deck_or_404(deck_id)


@app.patch("/api/decks/{deck_id}")
def rename_deck(deck_id: str, req: RenameRequest):
    state = _deck_or_404(deck_id)
    state["name"] = req.name.strip() or state["name"]
    store.save(deck_id, state)
    return {"ok": True, "name": state["name"]}


@app.delete("/api/decks/{deck_id}")
def delete_deck(deck_id: str):
    _deck_or_404(deck_id)
    store.discard(deck_id)
    return {"ok": True}


@app.put("/api/decks/{deck_id}/notes")
def save_notes(deck_id: str, req: NotesRequest):
    state = _deck_or_404(deck_id)
    notes = _check_notes(req.notes)
    for s in state["slides"]:
        if str(s["n"]) in notes:
            s["notes"] = notes[str(s["n"])].strip()
    store.save(deck_id, state)
    return {"ok": True}


@app.get("/api/decks/{deck_id}/slides/{n}.jpg")
def slide_image(deck_id: str, n: int):
    state = _deck_or_404(deck_id)
    for s in state["slides"]:
        if s["n"] == n:
            return FileResponse(store.deck_dir(deck_id) / "slides" / s["image"], media_type="image/jpeg")
    raise HTTPException(404, "No such slide.")


@app.post("/api/decks/{deck_id}/suggest-notes")
def suggest_notes(deck_id: str, req: SuggestRequest):
    _deck_or_404(deck_id)
    if not llm.configured():
        raise HTTPException(400, "No notes model is configured. Set NOTES_LLM_BASE_URL and NOTES_LLM_MODEL (see README).")
    notes = _check_notes(req.notes)
    job = manager.submit("notes", lambda j: pipeline.suggest_notes(deck_id, j, notes, req.slides, req.sentences, req.language))
    return {"job_id": job.id}


@app.post("/api/decks/{deck_id}/render")
def render(deck_id: str, req: RenderRequest):
    _deck_or_404(deck_id)
    payload = req.model_dump()
    payload["notes"] = _check_notes(payload["notes"])
    payload["voice"] = payload["voice"] or config.TTS_VOICE
    job = manager.submit("render", lambda j: pipeline.render_deck(deck_id, j, payload))
    return {"job_id": job.id}


@app.get("/api/decks/{deck_id}/files/{name}")
def download(deck_id: str, name: str, inline: bool = False, vtt: bool = False):
    state = _deck_or_404(deck_id)
    if name not in pipeline.OUTPUT_FILES:
        raise HTTPException(404, "Unknown file.")
    path = store.deck_dir(deck_id) / "out" / name
    if not path.exists():
        raise HTTPException(404, "Not rendered yet.")
    if vtt and name.endswith(".srt"):  # for the in-page player's subtitle tracks
        return Response(video.srt_to_vtt(path.read_text(encoding="utf-8")), media_type="text/vtt; charset=utf-8")
    return FileResponse(
        path,
        filename=f"{pipeline._safe_name(state['name'])}-{name}",
        content_disposition_type="inline" if inline else "attachment",
    )


# ---------- My voices (voice cloning) ----------

def _clone_base() -> str:
    if not config.CLONE_TTS_URL:
        raise HTTPException(404, "Voice cloning isn't set up. Start it with: docker compose --profile clone up -d")
    return config.CLONE_TTS_URL


def _clone_call(method: str, path: str, **kw):
    try:
        resp = httpx.request(method, f"{_clone_base()}{path}", timeout=60, **kw)
    except httpx.HTTPError:
        raise HTTPException(503, "The voice-cloning service isn't answering. Check: docker compose logs cloner")
    try:
        body = resp.json()
    except ValueError:
        body = {"detail": resp.text[:300]}
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, body.get("detail", "Voice cloning failed."))
    return body


@app.get("/api/my-voices")
def my_voices():
    return _clone_call("GET", "/voices")


@app.post("/api/my-voices")
async def add_my_voice(name: str = Form(...), consent: bool = Form(False), file: UploadFile = File(...),
                       start: float = Form(0.0, ge=0, le=3600), transcript: str = Form("", max_length=1000)):
    data = await file.read()
    return _clone_call("POST", "/voices", data={"name": name, "consent": str(consent).lower(), "start": str(start),
                                                "transcript": transcript},
                       files={"file": (file.filename or "clip.webm", data, file.content_type or "application/octet-stream")})


@app.delete("/api/my-voices/{voice_id}")
def delete_my_voice(voice_id: str):
    return _clone_call("DELETE", f"/voices/{voice_id}")


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job (the app may have restarted).")
    return job.to_dict()
