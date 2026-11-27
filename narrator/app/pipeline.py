"""The three long-running operations: prepare a deck, write notes with an LLM, render the video."""
from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path

from . import llm, pptx_tools, presenton, store, tts, video
from .jobs import Job

# code -> (English name used in prompts, ISO 639-2 code for MP4 tracks, native label)
SUBTITLE_LANGUAGES = {
    "en": ("English", "eng", "English"),
    "sq": ("Albanian", "sqi", "Shqip"),
    "it": ("Italian", "ita", "Italiano"),
    "pt": ("Portuguese", "por", "Português"),
    "no": ("Norwegian (Bokmål)", "nor", "Norsk"),
    "tr": ("Turkish", "tur", "Türkçe"),
}

OUTPUT_FILES = {
    "narrated.mp4": "Narrated video (MP4)",
    "narration-audio.zip": "Audio, one MP3 per slide (ZIP)",
    "narration.srt": "Subtitles (SRT)",
    "narration-subtitles.zip": "Subtitles in all languages (ZIP)",
    **{f"narration.{c}.srt": f"Subtitles, {v[0]} (SRT)" for c, v in SUBTITLE_LANGUAGES.items()},
    "deck-with-notes.pptx": "Deck with the final notes (PPTX)",
}

_KOKORO_LANG = {"a": "en", "b": "en", "i": "it", "p": "pt", "e": "es", "f": "fr"}


def guess_language(voice: str | None) -> str | None:
    """Best guess of the narration language from the voice name."""
    v = (voice or "").lower()
    if v.startswith(("sq_", "sq-")):
        return "sq"
    if len(v) > 2 and v[2] == "_" and v[1] in "fm":
        return _KOKORO_LANG.get(v[0])
    return None


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


def suggest_notes(deck_id: str, job: Job, current: dict[str, str], only: list[int] | None, sentences: int,
                  language: str | None = None) -> dict:
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
            notes[str(s["n"])] = llm.write_notes(state["name"], s, len(slides), sentences, language)
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
    state["settings"] = {k: req.get(k) for k in ("voice", "speed", "pause", "silent_seconds", "resolution", "subtitle_languages", "emotion")}
    store.save(deck_id, state)

    if not any(tts.clean_for_speech(s["notes"]) for s in slides):
        raise pptx_tools.DeckError("No slide has narration text yet. Write notes first, or use “Write missing notes with AI”.")
    langs = [c for c in (req.get("subtitle_languages") or []) if c in SUBTITLE_LANGUAGES]
    source_lang = guess_language(req.get("voice"))
    if any(c != source_lang for c in langs) and not llm.configured():
        raise pptx_tools.DeckError("Translated subtitles need the notes AI. Set it up (see Services), or untick the extra languages.")

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
            audio.write_bytes(tts.speech(s["notes"], req["voice"], req["speed"], "mp3", req.get("emotion", "natural")))
            audio_files.append(audio)
            speech_len = video.probe_duration(audio)
        segment = seg_dir / f"seg-{s['n']:03d}.mp4"
        seg_len = video.make_segment(d / "slides" / s["image"], audio, segment, size, req["pause"], req["silent_seconds"])
        segments.append(segment)
        if audio is not None:
            srt_entries.append((clock, speech_len, tts.clean_for_speech(s["notes"])))
        clock += seg_len

    job.update("Joining slides into one video…", 0.86 if langs else 0.92)
    video.concat(segments, out / "narrated.mp4")
    shutil.rmtree(seg_dir, ignore_errors=True)

    cues = video.build_cues(srt_entries)
    (out / "narration.srt").write_text(video.srt_from_cues(cues), encoding="utf-8")
    warnings: list[str] = []
    tracks: list[tuple[Path, str, str]] = []
    if langs:
        lines = [c[2] for c in cues]
        for k, code in enumerate(langs):
            name, iso, label = SUBTITLE_LANGUAGES[code]
            job.update(f"Translating subtitles into {name}…", 0.87 + 0.08 * k / len(langs))
            path = out / f"narration.{code}.srt"
            try:
                texts = None if code == source_lang else llm.translate_lines(lines, name)
            except Exception as exc:
                warnings.append(f"{name} subtitles failed: {exc}")
                continue
            path.write_text(video.srt_from_cues(cues, texts), encoding="utf-8")
            tracks.append((path, iso, label))
        if source_lang not in langs:  # keep the original-language track too
            orig = SUBTITLE_LANGUAGES.get(source_lang or "", ("Original", "und", "Original"))
            tracks.insert(0, (out / "narration.srt", orig[1], orig[2]))
        if tracks:
            job.update("Adding subtitle tracks to the video…", 0.95)
            tmp = out / "narrated.subs.mp4"
            video.embed_subtitles(out / "narrated.mp4", tracks, tmp)
            tmp.replace(out / "narrated.mp4")
            with zipfile.ZipFile(out / "narration-subtitles.zip", "w", zipfile.ZIP_DEFLATED) as zf:
                for path, _, _ in tracks:
                    zf.write(path, path.name)

    job.update("Writing audio bundle and deck…", 0.97)
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
    return {"outputs": outputs, "seconds": round(clock, 1), "warnings": warnings}
