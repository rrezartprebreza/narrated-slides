"""The three long-running operations: prepare a deck, write notes with an LLM, render the video."""
from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path

from . import llm, pptx_tools, presenton, store, tts, video
from .jobs import Job

OUTPUT_FILES = {
    "narrated.mp4": "Narrated video (MP4)",
    "narration-audio.zip": "Audio, one MP3 per slide (ZIP)",
    "narration.srt": "Subtitles (SRT)",
    "deck-with-notes.pptx": "Deck with the final notes (PPTX)",
}


def _safe_name(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
    return cleaned or "deck"


def _build_state(deck_id: str, name: str) -> dict:
    d = store.deck_dir(deck_id)
    src = d / "source.pptx"
    slides = pptx_tools.extract_slides(src)
    return {"id": deck_id, "name": name, "created": time.time(), "slides": slides, "outputs": [], "settings": {}}


def prepare_deck(deck_id: str, job: Job, name: str) -> dict:
    d = store.deck_dir(deck_id)
    src = d / "source.pptx"
    try:
        job.update("Reading slides and speaker notes…", 0.1)
        state = _build_state(deck_id, name)
        job.update("Rendering slide images (this can take a minute)…", 0.25)
        images = pptx_tools.render_slide_images(src, d / "slides", state["slides"])
        for slide, image in zip(state["slides"], images):
            slide["image"] = image.name
        store.save(deck_id, state)
    except Exception:
        store.discard(deck_id)
        raise
    return {"deck_id": deck_id}


def generate_deck(deck_id: str, job: Job, req: dict) -> dict:
    d = store.deck_dir(deck_id)
    try:
        job.update("Presenton is writing the slides (can take several minutes)…", 0.05)
        presenton.generate_pptx(
            d / "source.pptx",
            prompt=req["prompt"],
            n_slides=req.get("n_slides"),
            tone=req.get("tone", "default"),
            verbosity=req.get("verbosity", "standard"),
            template=req.get("template", "general"),
        )
    except Exception:
        store.discard(deck_id)
        raise
    return prepare_deck(deck_id, job, name="Generated deck")


def suggest_notes(deck_id: str, job: Job, current: dict[str, str], only: list[int] | None, sentences: int) -> dict:
    state = store.load(deck_id)
    slides = state["slides"]
    targets = []
    for s in slides:
        has_text = bool((current.get(str(s["n"]), s["notes"]) or "").strip())
        if only is not None:
            if s["n"] in only:
                targets.append(s)
        elif not has_text:
            targets.append(s)
    if not targets:
        return {"notes": {}, "errors": {}}
    notes: dict[str, str] = {}
    errors: dict[str, str] = {}
    for i, s in enumerate(targets):
        job.update(f"Writing notes for slide {s['n']} ({i + 1} of {len(targets)})…", i / len(targets))
        try:
            notes[str(s["n"])] = llm.write_notes(state["name"], s, len(slides), sentences)
        except Exception as exc:
            errors[str(s["n"])] = str(exc)[:200]
    if not notes:
        first = next(iter(errors.values()))
        raise pptx_tools.DeckError(f"The notes model did not answer: {first}")
    return {"notes": notes, "errors": errors}


def render_deck(deck_id: str, job: Job, req: dict) -> dict:
    state = store.load(deck_id)
    d = store.deck_dir(deck_id)
    slides = state["slides"]

    for s in slides:
        if str(s["n"]) in req["notes"]:
            s["notes"] = req["notes"][str(s["n"])].strip()
    state["settings"] = {k: req[k] for k in ("voice", "speed", "pause", "silent_seconds", "resolution")}
    store.save(deck_id, state)

    if not any(tts.clean_for_speech(s["notes"]) for s in slides):
        raise pptx_tools.DeckError("No slide has narration text yet. Write notes first, or use “Write missing notes with AI”.")

    out = d / "out"
    shutil.rmtree(out, ignore_errors=True)
    audio_dir, seg_dir = out / "audio", out / "segments"
    audio_dir.mkdir(parents=True)
    seg_dir.mkdir(parents=True)
    size = (1920, 1080) if req["resolution"] == 1080 else (1280, 720)

    segments: list[Path] = []
    srt_entries: list[tuple[float, float, str]] = []
    audio_files: list[Path] = []
    clock = 0.0
    total = len(slides)
    for i, s in enumerate(slides):
        job.update(f"Slide {s['n']} of {total}: " + ("speaking…" if s["notes"] else "no notes, silent slide…"), 0.02 + 0.88 * i / total)
        audio: Path | None = None
        speech_len = 0.0
        if tts.clean_for_speech(s["notes"]):
            audio = audio_dir / f"slide-{s['n']:02d}.mp3"
            audio.write_bytes(tts.speech(s["notes"], req["voice"], req["speed"], "mp3"))
            audio_files.append(audio)
            speech_len = video.probe_duration(audio)
        segment = seg_dir / f"seg-{s['n']:03d}.mp4"
        seg_len = video.make_segment(d / "slides" / s["image"], audio, segment, size, req["pause"], req["silent_seconds"])
        segments.append(segment)
        if audio is not None:
            srt_entries.append((clock, speech_len, tts.clean_for_speech(s["notes"])))
        clock += seg_len

    job.update("Joining slides into one video…", 0.92)
    video.concat(segments, out / "narrated.mp4")
    shutil.rmtree(seg_dir, ignore_errors=True)

    job.update("Writing subtitles, audio bundle and deck…", 0.96)
    (out / "narration.srt").write_text(video.build_srt(srt_entries), encoding="utf-8")
    with zipfile.ZipFile(out / "narration-audio.zip", "w", zipfile.ZIP_STORED) as zf:
        for f in audio_files:
            zf.write(f, f.name)
    pptx_tools.write_notes(d / "source.pptx", out / "deck-with-notes.pptx", {s["source_index"]: s["notes"] for s in slides})
    shutil.rmtree(audio_dir, ignore_errors=True)

    outputs = []
    for fname, label in OUTPUT_FILES.items():
        path = out / fname
        if path.exists():
            outputs.append({"name": fname, "label": label, "bytes": path.stat().st_size})
    state["outputs"] = outputs
    state["rendered"] = time.time()
    store.save(deck_id, state)
    return {"outputs": outputs, "seconds": round(clock, 1)}
