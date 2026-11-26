"""FFmpeg helpers: one MP4 segment per slide, concatenation, and SRT subtitles."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

FPS = 15


class VideoError(Exception):
    pass


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise VideoError(f"ffmpeg failed: {proc.stderr.strip()[-500:]}")


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise VideoError(f"Could not read the duration of {path.name}") from exc


def make_segment(
    image: Path,
    audio: Path | None,
    out: Path,
    size: tuple[int, int],
    pause: float,
    silent_seconds: float,
) -> float:
    """Still image + (narration | silence) -> MP4. Returns the segment duration."""
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "5", "-i", str(image)]
    if audio is not None:
        cmd += ["-i", str(audio), "-af", f"apad=pad_dur={pause:.2f}"]
        tail = ["-shortest"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        tail = ["-t", f"{silent_seconds:.2f}"]
    cmd += [
        "-vf", vf,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "23", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        *tail,
        "-movflags", "+faststart",
        str(out),
    ]
    _run(cmd)
    return probe_duration(out)


def concat(segments: list[Path], out: Path) -> None:
    listing = out.parent / "segments.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in segments), encoding="utf-8")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", "-movflags", "+faststart", str(out)])
    listing.unlink(missing_ok=True)


# ---------- subtitles ----------

def split_cues(text: str, max_chars: int = 84) -> list[str]:
    """Break narration into subtitle-sized pieces, preferring sentence ends."""
    pieces: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = sentence.strip()
        while len(sentence) > int(max_chars * 1.4):
            cut = max(sentence.rfind(", ", 0, max_chars), sentence.rfind("; ", 0, max_chars))
            if cut < max_chars // 2:
                cut = sentence.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            pieces.append(sentence[: cut + 1].strip())
            sentence = sentence[cut + 1:].strip()
        if sentence:
            pieces.append(sentence)
    cues: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > max_chars:
            cues.append(current)
            current = piece
        else:
            current = f"{current} {piece}".strip()
    if current:
        cues.append(current)
    return cues


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(entries: list[tuple[float, float, str]]) -> str:
    """entries: (start_seconds, speech_duration_seconds, text) per slide."""
    lines: list[str] = []
    idx = 1
    for start, duration, text in entries:
        cues = split_cues(text)
        total_chars = sum(len(c) for c in cues) or 1
        t = start
        for cue in cues:
            span = duration * len(cue) / total_chars
            lines += [str(idx), f"{_ts(t)} --> {_ts(t + span)}", cue, ""]
            t += span
            idx += 1
    return "\n".join(lines)
