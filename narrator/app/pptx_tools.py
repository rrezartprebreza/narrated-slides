"""Reading a PPTX (titles, text, speaker notes), writing notes back, rendering slide images."""
from __future__ import annotations

import glob
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from . import config

_soffice_lock = threading.Lock()  # LibreOffice does not like parallel conversions


class DeckError(Exception):
    """A problem with the uploaded deck that the user can act on."""


def _is_hidden(slide) -> bool:
    return slide._element.get("show") == "0"


def _shape_texts(shape) -> list[str]:
    texts: list[str] = []
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            texts.extend(_shape_texts(child))
    elif getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                texts.append(" | ".join(cells))
    elif shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            texts.append(text)
    return texts


def extract_slides(pptx_path: Path) -> list[dict]:
    """Return one dict per *visible* slide, in presentation order."""
    try:
        prs = Presentation(str(pptx_path))
    except Exception as exc:  # corrupt / not a pptx
        raise DeckError(f"Could not open the file as a PowerPoint (.pptx): {exc}") from exc

    slides = []
    for source_index, slide in enumerate(prs.slides):
        if _is_hidden(slide):
            continue
        title_shape = slide.shapes.title
        title = title_shape.text_frame.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
        body: list[str] = []
        for shape in slide.shapes:
            if title_shape is not None and shape.shape_id == title_shape.shape_id:
                continue
            body.extend(_shape_texts(shape))
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        slides.append(
            {
                "n": len(slides) + 1,
                "source_index": source_index,
                "title": title,
                "text": "\n".join(body),
                "notes": notes,
            }
        )
    if not slides:
        raise DeckError("The deck has no visible slides.")
    return slides


def count_all_slides(pptx_path: Path) -> int:
    return len(Presentation(str(pptx_path)).slides)


def write_notes(src: Path, dst: Path, notes_by_source_index: dict[int, str]) -> None:
    """Copy `src` to `dst` with the given speaker notes written into each slide."""
    prs = Presentation(str(src))
    for idx, slide in enumerate(prs.slides):
        if idx not in notes_by_source_index:
            continue
        wanted = notes_by_source_index[idx].strip()
        current = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            current = slide.notes_slide.notes_text_frame.text.strip()
        if wanted == current:
            continue
        frame = slide.notes_slide.notes_text_frame  # creates a notes slide if missing
        if frame is not None:
            frame.text = wanted
    prs.save(str(dst))


def _convert_to_pdf(pptx_path: Path, out_dir: Path) -> Path:
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    cmd = shlex.split(config.SOFFICE_CMD) + [
        "--headless",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(pptx_path),
    ]
    try:
        with _soffice_lock:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise DeckError("Rendering the slides took too long (LibreOffice timed out).") from exc
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    pdf = out_dir / (pptx_path.stem + ".pdf")
    if proc.returncode != 0 or not pdf.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise DeckError(f"LibreOffice could not render the deck. {tail}")
    return pdf


def render_slide_images(pptx_path: Path, out_dir: Path, visible: list[dict], width: int = 1920) -> list[Path]:
    """Render slides to JPEGs, returned in the order of `visible` (hidden slides skipped)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="render_"))
    try:
        pdf = _convert_to_pdf(pptx_path, work)
        prefix = work / "page"
        proc = subprocess.run(
            ["pdftoppm", "-jpeg", "-jpegopt", "quality=88", "-scale-to-x", str(width), "-scale-to-y", "-1", str(pdf), str(prefix)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            raise DeckError(f"Could not turn the PDF into images: {proc.stderr.strip()[-300:]}")
        pages = sorted(
            (Path(p) for p in glob.glob(str(prefix) + "-*.jpg")),
            key=lambda p: int(re.search(r"-(\d+)\.jpg$", p.name).group(1)),
        )
        total = count_all_slides(pptx_path)
        if len(pages) == len(visible):
            chosen = pages
        elif len(pages) == total:  # LibreOffice exported hidden slides too
            chosen = [pages[s["source_index"]] for s in visible]
        else:
            raise DeckError(
                f"Slide count mismatch: the deck has {total} slides ({len(visible)} visible) "
                f"but {len(pages)} pages were rendered."
            )
        result = []
        for slide, page in zip(visible, chosen):
            dest = out_dir / f"slide-{slide['n']:03d}.jpg"
            shutil.copyfile(page, dest)
            result.append(dest)
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)
