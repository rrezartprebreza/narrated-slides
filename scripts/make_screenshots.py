"""Drive the UI against mock TTS/LLM servers and save the screenshots used in the docs.

Needs the dev extras:  pip install -r narrator/requirements.txt pytest playwright && playwright install chromium
Also needs LibreOffice, ffmpeg and poppler on the PATH (the same things the Docker image installs).

    python scripts/make_screenshots.py            # writes docs/images/*.png
    python scripts/make_screenshots.py --check    # just runs the flow and prints what it saw
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "narrator"))
sys.path.insert(0, str(ROOT / "narrator" / "tests"))

from app import config  # noqa: E402
import test_e2e as t  # noqa: E402


def demo_llm_app():
    """Stands in for Ollama so the 'Write with AI' button has something to call."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/v1/models")
    def models():
        return {"data": []}

    @app.post("/v1/chat/completions")
    def chat():
        text = ("That's it. Upload your own deck, add notes to each slide, pick a voice, and export. "
                "Your first video takes only a couple of minutes.")
        return {"choices": [{"message": {"content": text}}]}

    return app


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run the flow without writing screenshots")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "images")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp())
    deck = t.make_deck(work / "Quarterly Review.pptx")
    config.DATA_DIR = work / "data"
    config.TTS_BASE_URL = t._serve(t._tts_app()) + "/v1"
    config.NOTES_LLM_BASE_URL = t._serve(demo_llm_app()) + "/v1"
    config.NOTES_LLM_MODEL = "demo-model"
    config.PRESENTON_URL = t._serve(t._presenton_app(deck.read_bytes()))
    config.EXTRA_TTS_BASE_URL = t._serve(t._piper_app()) + "/v1"
    config.CLONE_TTS_URL = t._serve(t._cloner_app(work / "voices")[0])
    config.SOFFICE_CMD = os.environ.get("TEST_SOFFICE_CMD", "soffice")
    from app.main import app

    base = t._serve(app)

    from playwright.sync_api import sync_playwright

    errors: list[str] = []

    def shot(page, name, full=False):
        page.evaluate("document.querySelector('#toasts').replaceChildren()")
        if not args.check:
            page.screenshot(path=str(args.out / f"{name}.png"), full_page=full)

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=1.5, color_scheme="light")
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))

        pg.goto(base)
        pg.wait_for_function("document.querySelector('#status-text').textContent === 'Ready'")
        shot(pg, "01-home")

        pg.click("#btn-sample")
        pg.wait_for_selector(".film button", timeout=120000)
        pg.wait_for_function("[...document.images].every(i => i.complete)")
        print("slides in filmstrip:", pg.locator(".film button").count())
        pg.click(".film button[data-n='2']")
        shot(pg, "02-script")

        pg.click(".film button[data-n='5']")
        pg.click("#view-script .notes-foot .btn:has-text('Write with AI')")
        pg.wait_for_function("document.querySelector('.notes-input').value.length > 0", timeout=60000)
        print("AI note for slide 5:", pg.input_value(".notes-input"))
        pg.click("#view-script .notes-foot .btn:has-text('Preview voice')")
        pg.wait_for_timeout(600)
        pg.click("#view-script .notes-foot .btn:has-text('Stop')") if pg.locator("#view-script .notes-foot .btn:has-text('Stop')").count() else None

        pg.click("text=Voice & export")
        pg.wait_for_selector("#voice")
        for code in ("sq", "it", "tr"):
            pg.check(f".chips input[value='{code}']")
        shot(pg, "03-export")
        pg.click("text=Create narrated video")
        pg.wait_for_selector(".done-banner", timeout=240000)
        pg.wait_for_timeout(500)
        print("downloads:", pg.locator(".dl-list a").all_inner_texts())
        pg.wait_for_function("document.querySelector('#player').readyState >= 2", timeout=30000)
        pg.set_viewport_size({"width": 1280, "height": 1240})  # tall viewport instead of full_page (sticky header)
        pg.evaluate("window.scrollTo(0, 0)")
        shot(pg, "04-result")
        pg.set_viewport_size({"width": 1280, "height": 860})

        pg.click("#btn-status")
        pg.wait_for_selector("#dlg-status .svc")
        shot(pg, "05-services")
        pg.keyboard.press("Escape")

        pg.click("#btn-theme")
        pg.goto(base)
        pg.wait_for_selector("#recent:not([hidden])")
        shot(pg, "06-home-dark")

        m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="light").new_page()
        m.on("pageerror", lambda e: errors.append(str(e)))
        m.goto(base)
        m.wait_for_selector("#recent:not([hidden])")
        shot(m, "07-mobile")
        b.close()

    print("console errors:", errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
