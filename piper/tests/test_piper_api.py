"""API tests with a fake Piper voice (the real model is downloaded only inside Docker)."""
import struct
import sys
import types
import wave

from fastapi.testclient import TestClient

from app import main


class FakeVoice:
    def synthesize_wav(self, text, wf, syn_config=None):
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
        frames = int(22050 * 0.3 * (syn_config.length_scale if syn_config else 1))
        wf.writeframes(struct.pack("<h", 0) * frames)


def _client(loaded):
    fake_piper = types.SimpleNamespace(SynthesisConfig=lambda length_scale=1.0: types.SimpleNamespace(length_scale=length_scale))
    sys.modules["piper"] = fake_piper
    main.voices.loaded = loaded
    main.voices.start = lambda: None
    return TestClient(main.app)


def test_parse_voices():
    assert main.parse_voices("a=http://x/a.onnx, b=http://y/b.onnx,,bad") == {"a": "http://x/a.onnx", "b": "http://y/b.onnx"}


def test_loading_then_ready():
    with _client({}) as c:
        assert c.get("/health").status_code == 503
        assert c.post("/v1/audio/speech", json={"input": "Mirëdita", "voice": "sq_edon"}).status_code == 503
    with _client({"sq_edon": FakeVoice()}) as c:
        assert c.get("/health").json()["status"] == "ready"
        assert c.get("/v1/audio/voices").json() == {"voices": ["sq_edon"]}
        mp3 = c.post("/v1/audio/speech", json={"input": "Mirëdita, si jeni?", "voice": "sq_edon", "speed": 1.2})
        assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg" and len(mp3.content) > 200
        wav = c.post("/v1/audio/speech", json={"input": "Faleminderit", "voice": "sq_edon", "response_format": "wav"})
        assert wav.content[:4] == b"RIFF"
        assert c.post("/v1/audio/speech", json={"input": "x", "voice": "nope"}).status_code == 400
