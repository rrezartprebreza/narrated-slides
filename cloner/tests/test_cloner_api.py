"""API tests with a fake model (the real one is downloaded only inside Docker)."""
import subprocess

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main


class FakeTensor:
    def __init__(self, n):
        self.a = np.zeros(n, dtype=np.float32)

    def squeeze(self):
        return self

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.a


class FakeModel:
    sr = 24000

    def __init__(self):
        self.calls = []

    def generate(self, text, audio_prompt_path=None):
        self.calls.append((text, audio_prompt_path))
        return FakeTensor(12000)


def clip(seconds: float) -> bytes:
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=200:duration={seconds}",
                           "-f", "mp3", "-"], capture_output=True, check=True).stdout


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(main.engine, "start", lambda: None)
    monkeypatch.setattr(main.engine, "model", None)
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
    fake = FakeModel()
    main.engine.model = fake
    assert client.get("/health").json()["status"] == "ready"
    r = client.post("/v1/audio/speech", json={"input": "Hello there. This is my cloned voice! Nice?", "voice": "clone_my_voice", "speed": 1.2})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 500
    assert [c[0] for c in fake.calls] == ["Hello there.", "This is my cloned voice!", "Nice?"]
    assert all(c[1].endswith("clone_my_voice.wav") for c in fake.calls)
    assert client.post("/v1/audio/speech", json={"input": "x", "voice": "af_heart"}).status_code == 400

    assert client.delete("/voices/clone_my_voice").json() == {"ok": True}
    assert client.delete("/voices/clone_my_voice").status_code == 404
    assert client.delete("/voices/../etc").status_code == 404
    assert [v["id"] for v in client.get("/voices").json()["voices"]] == ["clone_my_voice_2"]


def test_split_text_keeps_long_sentences_short():
    parts = main.split_text("word " * 200 + ". Short one.")
    assert all(len(p) <= 281 for p in parts) and parts[-1] == "Short one."
