"""Client for an OpenAI-compatible text-to-speech endpoint (Kokoro-FastAPI by default)."""
from __future__ import annotations

import re
import time

import httpx

from . import config


class TTSError(Exception):
    pass


def clean_for_speech(text: str) -> str:
    """Light normalisation so the engine does not read markup aloud."""
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s*\n+\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.TTS_API_KEY}"}


def _root(base: str) -> str:
    return base[: -len("/v1")] if base.endswith("/v1") else base


def _list(base: str) -> list[str]:
    resp = httpx.get(f"{base}/audio/voices", headers=_headers(), timeout=10)
    resp.raise_for_status()
    names = []
    for item in resp.json().get("voices", []):
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and (item.get("id") or item.get("name")):
            names.append(str(item.get("id") or item.get("name")))
    return names


_extra_voices: set[str] = set()


def _extra_list() -> list[str]:
    if not config.EXTRA_TTS_BASE_URL:
        return []
    try:
        names = _list(config.EXTRA_TTS_BASE_URL)
    except Exception:
        return sorted(_extra_voices)
    _extra_voices.clear()
    _extra_voices.update(names)
    return names


def engine_for(voice: str) -> tuple[str, str]:
    """(base_url, model) of the engine that has this voice."""
    if voice.startswith("clone_") and config.CLONE_TTS_URL:
        return f"{config.CLONE_TTS_URL}/v1", "chatterbox"
    if config.EXTRA_TTS_BASE_URL:
        if voice not in _extra_voices:
            _extra_list()
        if voice in _extra_voices:
            return config.EXTRA_TTS_BASE_URL, config.EXTRA_TTS_MODEL
    return config.TTS_BASE_URL, config.TTS_MODEL


# Emotion presets for cloned voices (Chatterbox: higher exaggeration = more expressive,
# lower cfg_weight = slower, more deliberate delivery that suits strong emotion).
EMOTIONS = {
    "calm": {"exaggeration": 0.3, "cfg_weight": 0.5},
    "natural": {"exaggeration": 0.5, "cfg_weight": 0.5},
    "lively": {"exaggeration": 0.8, "cfg_weight": 0.35},
    "dramatic": {"exaggeration": 1.2, "cfg_weight": 0.3},
}


def speech(text: str, voice: str | None = None, speed: float = 1.0, fmt: str = "mp3", emotion: str = "natural") -> bytes:
    text = clean_for_speech(text)
    if not text:
        raise TTSError("Nothing to say: the text is empty.")
    voice = voice or config.TTS_VOICE
    base, model = engine_for(voice)
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt,
        "speed": speed,
    }
    if voice.startswith("clone_"):
        payload.update(EMOTIONS.get(emotion, EMOTIONS["natural"]))
    last: Exception | None = None
    clone = voice.startswith("clone_")
    resets = 0
    # The TTS container can still be starting (first boot) - retry for a while. A cloned voice's
    # model takes a minute or two to load again after a restart, so it gets a longer window.
    for attempt in range(10 if clone else 6):
        try:
            resp = httpx.post(
                f"{base}/audio/speech",
                json=payload,
                headers=_headers(),
                timeout=config.TTS_TIMEOUT_S,
            )
            if resp.status_code < 400:
                if not resp.content:
                    raise TTSError("The TTS server returned empty audio.")
                return resp.content
            if resp.status_code < 500:  # client error: retrying will not help
                raise TTSError(f"TTS request rejected ({resp.status_code}): {resp.text[:300]}")
            last = TTSError(f"TTS server error {resp.status_code}: {resp.text[:200]}")
        except (httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError) as exc:
            # the service dropped the connection mid-request: it crashed or was killed
            resets += 1
            last = exc
            if resets >= 3:
                break
        except httpx.TransportError as exc:  # not up yet, or timed out
            last = exc
        time.sleep(min(2 ** attempt, 20))
    if resets:
        hint = ("The voice-cloning service stopped while speaking, usually because Docker ran out of memory. "
                "Give Docker Desktop more memory (Settings, Resources, Memory: 12 GB or more), or stop Ollama and "
                "Presenton while exporting with your own voice, then try again.") if clone else (
                "The voice service stopped while speaking, usually because Docker ran out of memory. "
                "Give Docker Desktop more memory (Settings, Resources), then try again.")
        raise TTSError(hint)
    raise TTSError(f"Could not reach the TTS server at {base}: {last}")


def voices() -> list[str]:
    try:
        main = _list(config.TTS_BASE_URL) or list(config.DEFAULT_VOICES)
    except Exception:
        main = list(config.DEFAULT_VOICES)
    extra = [v for v in _extra_list() if v not in main]
    clones: list[str] = []
    if config.CLONE_TTS_URL:
        try:
            clones = _list(f"{config.CLONE_TTS_URL}/v1")
        except Exception:
            clones = []
    return sorted(main) + sorted(extra) + sorted(clones)


def _up(base: str) -> bool:
    for url in (f"{_root(base)}/health", f"{base}/audio/voices"):
        try:
            if httpx.get(url, headers=_headers(), timeout=3).status_code < 500:
                return True
        except Exception:
            continue
    return False


def healthy() -> bool:
    return _up(config.TTS_BASE_URL)


def extra_healthy() -> bool | None:
    """None when no extra engine is configured; False while it is down or still downloading voices."""
    if not config.EXTRA_TTS_BASE_URL:
        return None
    return _up(config.EXTRA_TTS_BASE_URL) and bool(_extra_list())


def clone_healthy() -> bool | None:
    """None when voice cloning is not set up; False while its model is still loading or it is down."""
    if not config.CLONE_TTS_URL:
        return None
    try:
        return httpx.get(f"{config.CLONE_TTS_URL}/health", timeout=3).status_code == 200
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return None  # the optional cloner container isn't running
    except Exception:
        return False


def clone_model() -> str | None:
    """Which cloning engine is running: turbo, standard or qwen (None when it can't be reached)."""
    if not config.CLONE_TTS_URL:
        return None
    try:
        return httpx.get(f"{config.CLONE_TTS_URL}/health", timeout=3).json().get("model")
    except Exception:
        return None


def clone_supports_emotion() -> bool:
    """True when the cloner runs the expressive (standard) model rather than Turbo."""
    if not config.CLONE_TTS_URL:
        return False
    try:
        return bool(httpx.get(f"{config.CLONE_TTS_URL}/health", timeout=3).json().get("emotion"))
    except Exception:
        return False
