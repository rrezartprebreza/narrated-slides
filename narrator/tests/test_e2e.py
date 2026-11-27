"""End-to-end test of the narrator pipeline against stand-in TTS / LLM / Presenton servers.

Needs ffmpeg, poppler-utils and LibreOffice on the machine (they are in the Docker image):
    pip install -r requirements.txt pytest
    pytest tests -q
Set TEST_SOFFICE_CMD if LibreOffice is not started with plain `soffice`.
"""
import io
import os
import socket
import subprocess
import threading
import time
import zipfile
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from pptx import Presentation

from app import config, video


# ---------- helpers ----------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(app: FastAPI) -> str:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}"


def make_deck(path: Path) -> Path:
    """5 slides: notes / notes / none / HIDDEN with notes / notes."""
    prs = Presentation()
    texts = [
        ("Welcome", "Why this matters", "Hello and welcome to the talk."),
        ("The problem", "Slow reports", "Reports take hours to build by hand."),
        ("The idea", "Automate it", ""),
        ("Hidden backup", "Not shown", "This hidden slide must never be spoken."),
        ("Thanks", "Questions?", "Thank you for listening."),
    ]
    for title, sub, note in texts:
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = title
        slide.placeholders[1].text = sub
        if note:
            slide.notes_slide.notes_text_frame.text = note
    prs.slides[3]._element.set("show", "0")
    prs.save(str(path))
    return path


# ---------- stand-in servers ----------

def _tts_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/v1/audio/voices")
    def voices():
        return {"voices": ["af_heart", "am_michael"]}

    @app.post("/v1/audio/speech")
    async def speech(req: Request):
        body = await req.json()
        assert body["model"] == "kokoro" and body["response_format"] == "mp3"
        seconds = max(1.0, len(body["input"]) / 14)
        mp3 = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
             "-f", "mp3", "-"],
            capture_output=True, check=True,
        ).stdout
        return Response(mp3, media_type="audio/mpeg")

    return app


def _piper_app() -> FastAPI:
    """Stands in for the Piper (Albanian) engine."""
    app = FastAPI()
    calls: list[dict] = []
    app.state.calls = calls

    @app.get("/health")
    def health():
        return {"status": "ready"}

    @app.get("/v1/audio/voices")
    def voices():
        return {"voices": ["sq_edon"]}

    @app.post("/v1/audio/speech")
    async def speech(req: Request):
        body = await req.json()
        calls.append(body)
        assert body["model"] == "piper" and body["voice"] == "sq_edon"
        mp3 = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=1.5", "-f", "mp3", "-"],
            capture_output=True, check=True,
        ).stdout
        return Response(mp3, media_type="audio/mpeg")

    return app


def _llm_app() -> FastAPI:
    app = FastAPI()

    @app.get("/v1/models")
    def models():
        return {"data": []}

    @app.post("/v1/chat/completions")
    async def chat(req: Request):
        body = await req.json()
        user = body["messages"][-1]["content"]
        if user.startswith("Translate"):  # subtitle translation: answer a JSON array, one item per line
            import json as _json
            lang = user.split(" into ", 1)[1].split(":", 1)[0]
            lines = _json.loads(user.split("\n", 1)[1])
            return {"choices": [{"message": {"content": "```json\n" + _json.dumps([f"[{lang}] {x}" for x in lines]) + "\n```"}}]}
        assert "The idea" in user  # slide content was passed through
        return {"choices": [{"message": {"content": "Narration: **Automation** removes the manual steps."}}]}

    return app


def _presenton_app(deck_bytes: bytes) -> FastAPI:
    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    @app.post("/api/v1/ppt/presentation/generate")
    async def generate(req: Request):
        body = await req.json()
        assert body["content"] and body["export_as"] == "pptx"
        return {"presentation_id": "abc", "path": "/app_data/exports/abc.pptx", "edit_path": "/presentation?id=abc"}

    @app.get("/app_data/exports/abc.pptx")
    def download():
        return Response(deck_bytes, media_type="application/octet-stream")

    return app


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def deck_file(tmp_path_factory) -> Path:
    return make_deck(tmp_path_factory.mktemp("deck") / "Quarterly Review.pptx")


@pytest.fixture(scope="module")
def client(tmp_path_factory, deck_file):
    mp = pytest.MonkeyPatch()
    tts_url = _serve(_tts_app())
    llm_url = _serve(_llm_app())
    presenton_url = _serve(_presenton_app(deck_file.read_bytes()))
    piper = _piper_app()
    piper_url = _serve(piper)
    mp.setattr(config, "DATA_DIR", tmp_path_factory.mktemp("data"))
    mp.setattr(config, "TTS_BASE_URL", tts_url + "/v1")
    mp.setattr(config, "NOTES_LLM_BASE_URL", llm_url + "/v1")
    mp.setattr(config, "NOTES_LLM_MODEL", "test-model")
    mp.setattr(config, "PRESENTON_URL", presenton_url)
    mp.setattr(config, "EXTRA_TTS_BASE_URL", piper_url + "/v1")
    mp.setattr(config, "SOFFICE_CMD", os.environ.get("TEST_SOFFICE_CMD", "soffice"))
    from app.main import app

    with TestClient(app) as c:
        c.piper_calls = piper.state.calls
        yield c
    mp.undo()


def wait(client, job_id, timeout=300) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.5)
    raise AssertionError("job timed out")


def upload(client, path: Path) -> str:
    with open(path, "rb") as fh:
        r = client.post("/api/decks", files={"file": (path.name, fh)})
    assert r.status_code == 200, r.text
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    return r.json()["deck_id"]


# ---------- tests ----------

def test_health_and_voices(client):
    h = client.get("/api/health").json()
    assert h["tts"] and h["llm"] and h["presenton"]
    assert client.get("/api/voices").json()["voices"] == ["af_heart", "am_michael", "sq_edon"]
    assert client.get("/api/health").json()["extra_tts"] is True


def test_upload_reads_visible_slides_and_notes(client, deck_file):
    deck_id = upload(client, deck_file)
    deck = client.get(f"/api/decks/{deck_id}").json()
    assert deck["name"] == "Quarterly Review"
    assert [s["title"] for s in deck["slides"]] == ["Welcome", "The problem", "The idea", "Thanks"]  # hidden skipped
    assert [bool(s["notes"]) for s in deck["slides"]] == [True, True, False, True]
    img = client.get(f"/api/decks/{deck_id}/slides/4.jpg")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and len(img.content) > 2000


def test_suggest_then_render(client, deck_file):
    deck_id = upload(client, deck_file)
    r = client.post(f"/api/decks/{deck_id}/suggest-notes", json={"notes": {}})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert list(job["result"]["notes"]) == ["3"]  # only the empty slide
    assert job["result"]["notes"]["3"] == "Automation removes the manual steps."  # prefix + markdown stripped

    notes = {"1": "Hello and welcome to the talk.", "3": job["result"]["notes"]["3"], "4": "Edited closing line."}
    r = client.post(f"/api/decks/{deck_id}/render", json={"notes": notes, "pause": 0.5, "resolution": 720})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    names = {o["name"] for o in job["result"]["outputs"]}
    assert names == {"narrated.mp4", "narration-audio.zip", "narration.srt", "deck-with-notes.pptx"}

    out = Path(config.DATA_DIR) / "decks" / deck_id / "out"
    # slide 2 keeps its original note, so 4 spoken slides, no silent one
    with zipfile.ZipFile(out / "narration-audio.zip") as zf:
        assert sorted(zf.namelist()) == ["slide-01.mp3", "slide-02.mp3", "slide-03.mp3", "slide-04.mp3"]
    dur = video.probe_duration(out / "narrated.mp4")
    assert dur > 4 * 1.0  # >= 1 s speech per slide
    assert abs(dur - job["result"]["seconds"]) < 0.5
    srt = (out / "narration.srt").read_text()
    assert "Edited closing line." in srt and "00:00:00,000 -->" in srt
    # edited notes were written back; the hidden slide was left alone
    prs = Presentation(str(out / "deck-with-notes.pptx"))
    assert prs.slides[4].notes_slide.notes_text_frame.text == "Edited closing line."
    assert prs.slides[3].notes_slide.notes_text_frame.text == "This hidden slide must never be spoken."
    # download endpoint
    assert client.get(f"/api/decks/{deck_id}/files/narrated.mp4").status_code == 200
    assert client.get(f"/api/decks/{deck_id}/files/../../state.json").status_code in (404, 422)


def test_silent_slide_and_render_without_any_notes(client, deck_file):
    deck_id = upload(client, deck_file)
    empty = {str(n): "" for n in range(1, 5)}
    r = client.post(f"/api/decks/{deck_id}/render", json={"notes": empty})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "error" and "No slide has narration" in job["error"]

    r = client.post(f"/api/decks/{deck_id}/render",
                    json={"notes": {**empty, "1": "Just one spoken slide."}, "silent_seconds": 2, "pause": 0, "resolution": 720})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert job["result"]["seconds"] >= 3 * 2 + 1  # three 2 s silent slides + one spoken


def test_generate_through_presenton(client):
    r = client.post("/api/decks/generate", json={"prompt": "A talk about reports", "n_slides": 5})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    deck = client.get(f"/api/decks/{r.json()['deck_id']}").json()
    assert deck["name"] == "Generated deck" and len(deck["slides"]) == 4


def test_bad_uploads_are_rejected_cleanly(client, tmp_path):
    assert client.post("/api/decks", files={"file": ("x.txt", b"hi")}).status_code == 400
    assert client.post("/api/decks", files={"file": ("x.pptx", b"not a zip")}).status_code == 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "zip but not a deck")
    r = client.post("/api/decks", files={"file": ("fake.pptx", buf.getvalue())})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "error" and "PowerPoint" in job["error"]
    assert client.get(f"/api/decks/{r.json()['deck_id']}").status_code == 404  # failed decks are removed
    assert client.get("/api/decks/not-an-id").status_code == 404


def test_tts_preview(client):
    r = client.post("/api/tts/preview", json={"text": "Testing one two three.", "speed": 1.1})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 500


def test_subtitle_splitting():
    cues = video.split_cues("First sentence here. Second one is a little longer than the first, with a comma in it. Third.")
    assert all(len(c) <= 120 for c in cues) and " ".join(cues).startswith("First sentence here.")
    assert video._ts(3661.5) == "01:01:01,500"


def test_sample_deck_list_rename_delete(client):
    r = client.get("/sample-deck.pptx")
    assert r.status_code == 200 and r.content[:2] == b"PK"

    r = client.post("/api/decks/sample")
    assert r.status_code == 200
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    deck_id = r.json()["deck_id"]
    deck = client.get(f"/api/decks/{deck_id}").json()
    assert deck["name"] == "Sample deck" and len(deck["slides"]) == 5

    listed = client.get("/api/decks").json()["decks"]
    entry = next(d for d in listed if d["id"] == deck_id)
    assert entry["slides"] == 5 and entry["rendered"] is False

    assert client.patch(f"/api/decks/{deck_id}", json={"name": "  My talk "}).json()["name"] == "My talk"
    assert client.patch(f"/api/decks/{deck_id}", json={"name": ""}).status_code == 422
    assert client.get(f"/api/decks/{deck_id}").json()["name"] == "My talk"

    assert client.delete(f"/api/decks/{deck_id}").json() == {"ok": True}
    assert client.get(f"/api/decks/{deck_id}").status_code == 404
    assert client.delete(f"/api/decks/{deck_id}").status_code == 404
    assert all(d["id"] != deck_id for d in client.get("/api/decks").json()["decks"])


def test_health_reports_version(client):
    assert client.get("/api/health").json()["version"]


def test_albanian_voice_goes_to_piper(client, deck_file):
    before = len(client.piper_calls)
    r = client.post("/api/tts/preview", json={"text": "Mirëdita! Si jeni sot?", "voice": "sq_edon"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert client.piper_calls[-1]["input"] == "Mirëdita! Si jeni sot?"  # ë kept intact
    deck_id = upload(client, deck_file)
    job = wait(client, client.post(f"/api/decks/{deck_id}/render", json={"voice": "sq_edon", "resolution": 720}).json()["job_id"])
    assert job["status"] == "done", job
    assert len(client.piper_calls) - before == 1 + 3  # preview + three narrated slides


def test_notes_language_follows_albanian_voice(client, deck_file, monkeypatch):
    from app import llm
    seen = []
    monkeypatch.setattr(llm.httpx, "post", lambda url, json, **kw: (seen.append(json["messages"][-1]["content"]),
                        type("R", (), {"raise_for_status": lambda self: None,
                                       "json": lambda self: {"choices": [{"message": {"content": "Mirëdita të gjithëve."}}]}})())[1])
    deck_id = upload(client, deck_file)
    job = wait(client, client.post(f"/api/decks/{deck_id}/suggest-notes", json={"slides": [3], "language": "Albanian"}).json()["job_id"])
    assert job["status"] == "done" and job["result"]["notes"]["3"] == "Mirëdita të gjithëve."
    assert "Write it in Albanian" in seen[-1]


def test_subtitles_in_several_languages(client, deck_file):
    deck_id = upload(client, deck_file)
    r = client.post(f"/api/decks/{deck_id}/render",
                    json={"voice": "af_heart", "resolution": 720, "subtitle_languages": ["sq", "en", "tr"]})
    job = wait(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert job["result"]["warnings"] == []
    names = {o["name"] for o in job["result"]["outputs"]}
    assert {"narration.srt", "narration.sq.srt", "narration.en.srt", "narration.tr.srt", "narration-subtitles.zip"} <= names

    original = client.get(f"/api/decks/{deck_id}/files/narration.srt").text
    sq = client.get(f"/api/decks/{deck_id}/files/narration.sq.srt").text
    en = client.get(f"/api/decks/{deck_id}/files/narration.en.srt").text
    assert en == original                       # English voice: English track is the original, not re-translated
    assert "[Albanian] " in sq and sq.count("-->") == original.count("-->")  # same timings
    assert "[Turkish] " in client.get(f"/api/decks/{deck_id}/files/narration.tr.srt").text

    vtt = client.get(f"/api/decks/{deck_id}/files/narration.sq.srt?vtt=1")
    assert vtt.text.startswith("WEBVTT") and "00:00:00.000 -->" in vtt.text

    mp4 = client.get(f"/api/decks/{deck_id}/files/narrated.mp4").content
    tmp = deck_file.parent / "subs.mp4"
    tmp.write_bytes(mp4)
    langs = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream_tags=language",
                            "-of", "csv=p=0", str(tmp)], capture_output=True, text=True, check=True).stdout.split()
    assert langs == ["sqi", "eng", "tur"]


def test_subtitle_languages_need_llm(client, deck_file, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "NOTES_LLM_BASE_URL", "")
    deck_id = upload(client, deck_file)
    job = wait(client, client.post(f"/api/decks/{deck_id}/render", json={"voice": "af_heart", "subtitle_languages": ["it"]}).json()["job_id"])
    assert job["status"] == "error" and "notes AI" in job["error"]
    # the narration's own language needs no AI
    job = wait(client, client.post(f"/api/decks/{deck_id}/render",
                                   json={"voice": "af_heart", "resolution": 720, "subtitle_languages": ["en"]}).json()["job_id"])
    assert job["status"] == "done", job


def test_parse_translation_array():
    from app import llm
    assert llm._parse_array('Sure! ```json\n["a", "b"]\n```', 2) == ["a", "b"]
    assert llm._parse_array('["a"]', 2) is None
    assert llm._parse_array("no json here", 1) is None


def _cloner_app(voices_dir):
    """The real cloner service with a fake model, so the whole My voices flow is exercised."""
    import importlib.util

    import numpy as np

    path = Path(__file__).resolve().parents[2] / "cloner" / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("cloner_main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.VOICES_DIR = voices_dir
    mod.engine.start = lambda: None

    class Out:
        def __init__(self):
            self.a = np.zeros(6000, dtype=np.float32)

        def squeeze(self):
            return self

        detach = cpu = squeeze

        def numpy(self):
            return self.a

    class Model:
        sr = 24000
        calls = []

        emotions = []

        def generate(self, text, audio_prompt_path=None, exaggeration=0.5, cfg_weight=0.5):
            Model.calls.append(text)
            Model.emotions.append((exaggeration, cfg_weight))
            return Out()

    mod.engine.model = Model()
    voices_dir.mkdir(parents=True, exist_ok=True)
    _cloner_app.emotions = Model.emotions
    return mod.app, Model.calls


def test_my_voice_clone_flow(client, deck_file, tmp_path, monkeypatch):
    from app import config

    # not set up -> clear message
    monkeypatch.setattr(config, "CLONE_TTS_URL", "")
    assert client.get("/api/health").json()["clone"] is None
    assert "--profile clone" in client.get("/api/my-voices").json()["detail"]

    cloner, calls = _cloner_app(tmp_path / "voices")
    monkeypatch.setattr(config, "CLONE_TTS_URL", _serve(cloner))
    assert client.get("/api/health").json()["clone"] is True

    rec = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=9", "-f", "webm",
                          "-c:a", "libopus", "-"], capture_output=True, check=True).stdout
    r = client.post("/api/my-voices", data={"name": "Rrezart", "consent": "false"}, files={"file": ("rec.webm", rec, "audio/webm")})
    assert r.status_code == 400 and "permission" in r.json()["detail"]
    r = client.post("/api/my-voices", data={"name": "Rrezart", "consent": "true"}, files={"file": ("rec.webm", rec, "audio/webm")})
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    assert vid == "clone_rrezart"
    assert client.get("/api/my-voices").json()["voices"][0]["name"] == "Rrezart"
    assert "clone_rrezart" in client.get("/api/voices").json()["voices"]

    r = client.post("/api/tts/preview", json={"text": "Hello students. Welcome back!", "voice": vid})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert calls[-2:] == ["Hello students.", "Welcome back!"]
    client.post("/api/tts/preview", json={"text": "Amazing!", "voice": vid, "emotion": "dramatic"})
    assert _cloner_app.emotions[-1] == (1.2, 0.3)

    deck_id = upload(client, deck_file)
    job = wait(client, client.post(f"/api/decks/{deck_id}/render", json={"voice": vid, "resolution": 720}).json()["job_id"])
    assert job["status"] == "done", job

    assert client.delete(f"/api/my-voices/{vid}").json() == {"ok": True}
    assert client.get("/api/my-voices").json()["voices"] == []


def test_voice_service_crash_gives_memory_hint(monkeypatch):
    import httpx as _httpx

    from app import config, tts

    monkeypatch.setattr(config, "CLONE_TTS_URL", "http://cloner.invalid:8000")
    monkeypatch.setattr(tts.time, "sleep", lambda s: None)
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        raise _httpx.ReadError("[Errno 104] Connection reset by peer")

    monkeypatch.setattr(tts.httpx, "post", boom)
    with pytest.raises(tts.TTSError) as err:
        tts.speech("Hello there.", "clone_me")
    assert "memory" in str(err.value) and len(calls) == 3
