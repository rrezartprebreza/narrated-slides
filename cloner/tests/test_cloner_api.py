"""API tests with a fake model (the real one is downloaded only when the service starts)."""
import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main


class FakeQwen:
    """Stands in for qwen_tts.Qwen3TTSModel."""

    def __init__(self, fail_sampling=False):
        self.prompts = []
        self.calls = []
        self.fail_sampling = fail_sampling

    def create_voice_clone_prompt(self, ref_audio, ref_text=None, x_vector_only_mode=False):
        self.prompts.append((ref_audio, ref_text, x_vector_only_mode))
        return [("prompt", ref_audio)]

    def generate_voice_clone(self, text, language=None, voice_clone_prompt=None, **kw):
        if self.fail_sampling and kw.get("do_sample") is not False:
            raise RuntimeError("probability tensor contains either inf, nan or element < 0")
        self.calls.append((text, language, voice_clone_prompt[0][1], kw.get("do_sample")))
        self.kwargs = kw
        return [np.zeros(6000, dtype=np.float32)], 24000


def clip(seconds: float) -> bytes:
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=200:duration={seconds}",
                           "-f", "mp3", "-"], capture_output=True, check=True).stdout


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(main.engine, "start", lambda: None)
    monkeypatch.setattr(main.engine, "model", None)
    monkeypatch.setattr(main.engine, "prompts", {})
    with TestClient(main.app) as c:
        yield c


def test_voice_lifecycle(client):
    assert client.get("/health").status_code == 503
    r = client.post("/voices", data={"name": "My Voice", "consent": "false"}, files={"file": ("a.mp3", clip(8))})
    assert r.status_code == 400 and "permission" in r.json()["detail"]
    r = client.post("/voices", data={"name": "My Voice", "consent": "true"}, files={"file": ("a.mp3", clip(2))})
    assert r.status_code == 400 and "too short" in r.json()["detail"]
    r = client.post("/voices", data={"name": "My Voice", "consent": "true"}, files={"file": ("a.mp3", clip(30))})
    assert r.status_code == 200, r.text
    voice = r.json()
    assert voice["id"] == "clone_my_voice" and 19 <= voice["seconds"] <= 20.1  # trimmed to 20 s
    again = client.post("/voices", data={"name": "My Voice", "consent": "true"}, files={"file": ("a.mp3", clip(8))}).json()
    assert again["id"] == "clone_my_voice_2"
    assert client.get("/v1/audio/voices").json()["voices"] == ["clone_my_voice", "clone_my_voice_2"]

    # model still loading -> 503
    assert client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_my_voice"}).status_code == 503
    fake = FakeQwen()
    main.engine.model = fake
    assert client.get("/health").json()["status"] == "ready"
    r = client.post("/v1/audio/speech", json={"input": "Hello there. This is my cloned voice! Nice?", "voice": "clone_my_voice", "speed": 1.2})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 500
    assert [c[0] for c in fake.calls] == ["Hello there.", "This is my cloned voice!", "Nice?"]
    assert all(c[2].endswith("clone_my_voice.wav") for c in fake.calls)
    client.post("/v1/audio/speech", json={"input": "Again.", "voice": "clone_my_voice"})
    assert len(fake.prompts) == 1  # analysed once, then cached
    # a newly saved voice is analysed right away in the background
    client.post("/voices", data={"name": "Warm", "consent": "true"}, files={"file": ("a.mp3", clip(8))})
    for _ in range(50):
        if len(fake.prompts) > 1:
            break
        time.sleep(0.05)
    assert fake.prompts[-1][0].endswith("clone_warm.wav")
    assert client.post("/v1/audio/speech", json={"input": "x", "voice": "af_heart"}).status_code == 400

    assert client.delete("/voices/clone_my_voice").json() == {"ok": True}
    assert client.delete("/voices/clone_my_voice").status_code == 404
    assert client.delete("/voices/../etc").status_code == 404
    assert [v["id"] for v in client.get("/voices").json()["voices"]] == ["clone_my_voice_2", "clone_warm"]


def test_split_text_keeps_long_sentences_short():
    parts = main.split_text("word " * 200 + ". Short one.")
    assert all(len(p) <= 281 for p in parts) and parts[-1] == "Short one."


def test_video_upload_with_start_point(client):
    video = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=9",
                            "-f", "lavfi", "-i", "sine=frequency=180:duration=9", "-shortest", "-c:v", "libx264",
                            "-c:a", "aac", "-f", "mp4", "-movflags", "frag_keyframe+empty_moov", "-"],
                           capture_output=True, check=True).stdout
    r = client.post("/voices", data={"name": "Reel", "consent": "true", "start": "7"}, files={"file": ("reel.mp4", video, "video/mp4")})
    assert r.status_code == 400 and "too short" in r.json()["detail"]  # only 2 s left after skipping 7 s
    r = client.post("/voices", data={"name": "Reel", "consent": "true", "start": "1"}, files={"file": ("reel.mp4", video, "video/mp4")})
    assert r.status_code == 200, r.text
    assert 7 <= r.json()["seconds"] <= 8.2
    main.engine.model = FakeQwen()
    # older apps may still send Chatterbox emotion fields: ignored, not an error
    r = client.post("/v1/audio/speech", json={"input": "Wow!", "voice": "clone_reel", "exaggeration": 1.2})
    assert r.status_code == 200


def test_video_without_sound_is_explained(client):
    silent = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=9",
                             "-c:v", "libx264", "-f", "mp4", "-movflags", "frag_keyframe+empty_moov", "-"],
                            capture_output=True, check=True).stdout
    r = client.post("/voices", data={"name": "Silent", "consent": "true"}, files={"file": ("rec.mov", silent, "video/quicktime")})
    assert r.status_code == 400 and "no sound" in r.json()["detail"]


def test_qwen_engine_uses_transcript(client):
    said = "Hello, and welcome to my talk."
    r = client.post("/voices", data={"name": "Q", "consent": "true", "transcript": f"  {said}  "},
                    files={"file": ("a.mp3", clip(8))})
    assert r.status_code == 200 and r.json()["has_transcript"] and "transcript" not in r.json()
    long = client.post("/voices", data={"name": "Long", "consent": "true", "transcript": said},
                       files={"file": ("a.mp3", clip(30))}).json()
    assert not long["has_transcript"]  # cut at 20 s, so the transcript no longer matches
    plain = client.post("/voices", data={"name": "Plain", "consent": "true"}, files={"file": ("a.mp3", clip(8))}).json()
    assert not plain["has_transcript"]

    fake = FakeQwen()
    main.engine.model = fake
    health = client.get("/health").json()
    assert health["model"] == "qwen" and health["transcript"] is True
    r = client.post("/v1/audio/speech", json={"input": "One. Two.", "voice": "clone_q", "response_format": "wav"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert [c[0] for c in fake.calls] == ["One.", "Two."] and fake.calls[0][1] == "English"
    assert fake.prompts == [(str(main.VOICES_DIR / "clone_q.wav"), said, False)]
    client.post("/v1/audio/speech", json={"input": "Three.", "voice": "clone_q"})
    assert len(fake.prompts) == 1  # prompt cached per voice
    client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_plain"})
    assert fake.prompts[-1][1:] == (None, True)  # no transcript: speaker-embedding mode

    flaky = FakeQwen(fail_sampling=True)
    main.engine.model = flaky
    main.engine.prompts = {}
    r = client.post("/v1/audio/speech", json={"input": "Retry me.", "voice": "clone_q"})
    assert r.status_code == 200 and flaky.calls == [("Retry me.", "English", str(main.VOICES_DIR / "clone_q.wav"), False)]


def test_delivery_style_sets_sampling(client):
    client.post("/voices", data={"name": "S", "consent": "true"}, files={"file": ("a.mp3", clip(8))})
    fake = FakeQwen()
    main.engine.model = fake
    assert client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_s"}).status_code == 200
    assert "temperature" not in fake.kwargs  # natural: model defaults
    client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_s", "style": "expressive"})
    assert fake.kwargs["temperature"] > 1 and fake.kwargs["top_p"] == 0.95
    client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_s", "style": "steady"})
    assert fake.kwargs["temperature"] < 0.7
    assert client.post("/v1/audio/speech", json={"input": "Hi.", "voice": "clone_s", "style": "angry"}).status_code == 422
