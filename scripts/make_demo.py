"""Record a short demo of the UI (sample deck -> edit -> export) and save docs/images/demo.gif.

Same requirements as make_screenshots.py. Uses mock voice/LLM servers, so the GIF shows the UI only.
    python scripts/make_demo.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_screenshots as ms  # noqa: E402  (reuses the mock setup)


def main() -> int:
    work = Path(tempfile.mkdtemp())
    t = ms.t
    deck = t.make_deck(work / "deck.pptx")
    ms.config.DATA_DIR = work / "data"
    ms.config.TTS_BASE_URL = t._serve(t._tts_app()) + "/v1"
    ms.config.NOTES_LLM_BASE_URL = t._serve(ms.demo_llm_app()) + "/v1"
    ms.config.NOTES_LLM_MODEL = "demo-model"
    ms.config.PRESENTON_URL = t._serve(t._presenton_app(deck.read_bytes()))
    ms.config.SOFFICE_CMD = os.environ.get("TEST_SOFFICE_CMD", "soffice")
    from app.main import app

    base = t._serve(app)
    from playwright.sync_api import sync_playwright

    vids = work / "video"
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(vids),
                            record_video_size={"width": 1280, "height": 800}, color_scheme="light")
        pg = ctx.new_page()
        t0 = time.monotonic()
        pg.goto(base)
        pg.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
        pg.wait_for_timeout(1800)
        pg.hover("#btn-sample"); pg.wait_for_timeout(500)
        pg.click("#btn-sample")
        pg.wait_for_selector(".film button", timeout=120000)
        pg.wait_for_function("[...document.images].every(i => i.complete)")
        pg.wait_for_timeout(1500)
        for n in (2, 3):
            pg.click(f".film button[data-n='{n}']"); pg.wait_for_timeout(1100)
        pg.click(".film button[data-n='5']"); pg.wait_for_timeout(900)
        pg.click("#view-script .notes-foot .btn:has-text('Write with AI')")
        pg.wait_for_function("document.querySelector('.notes-input').value.length > 0", timeout=60000)
        pg.wait_for_timeout(1800)
        pg.click("text=Voice & export"); pg.wait_for_selector("#voice"); pg.wait_for_timeout(1500)
        pg.click("text=Create narrated video")
        r0 = time.monotonic() - t0 + 1.0
        pg.wait_for_selector(".done-banner", timeout=240000)
        r1 = time.monotonic() - t0
        pg.wait_for_function("document.querySelector('#player').readyState >= 2", timeout=30000)
        pg.evaluate("document.querySelector('.result').scrollIntoView({behavior:'smooth'})")
        pg.wait_for_timeout(3000)
        ctx.close(); b.close()

    webm = next(vids.glob("*.webm"))
    out = ROOT / "docs" / "images"
    palette = work / "pal.png"
    # play the long render step 5x faster
    speed = (f"[0:v]trim=0:{r0:.2f},setpts=PTS-STARTPTS[a];"
             f"[0:v]trim={r0:.2f}:{r1:.2f},setpts=(PTS-STARTPTS)/5[b];"
             f"[0:v]trim=start={r1:.2f},setpts=PTS-STARTPTS[c];[a][b][c]concat=n=3:v=1[v]")
    fast = work / "fast.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-filter_complex", speed, "-map", "[v]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast", str(fast)], check=True)
    webm = fast
    flt = "fps=10,scale=960:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-vf", f"{flt},palettegen=stats_mode=diff", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-i", str(palette),
                    "-lavfi", f"{flt}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5", str(out / "demo.gif")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "26", "-preset", "veryfast", "-movflags", "+faststart", str(work / "demo.mp4")], check=True)
    shutil.copy(work / "demo.mp4", ROOT / "docs" / "demo.mp4")
    print("wrote", out / "demo.gif", "and docs/demo.mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
