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
    if config.EXTRA_TTS_BASE_URL:
        if voice not in _extra_voices:
            _extra_list()
        if voice in _extra_voices:
            return config.EXTRA_TTS_BASE_URL, config.EXTRA_TTS_MODEL
    return config.TTS_BASE_URL, config.TTS_MODEL


def speech(text: str, voice: str | None = None, speed: float = 1.0, fmt: str = "mp3") -> bytes:
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
    last: Exception | None = None
    # The TTS container can still be starting (first boot) - retry for ~1 minute.
    for attempt in range(6):
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
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last = exc
        time.sleep(min(2 ** attempt, 15))
    raise TTSError(f"Could not reach the TTS server at {base}: {last}")


def voices() -> list[str]:
    try:
        main = _list(config.TTS_BASE_URL) or list(config.DEFAULT_VOICES)
    except Exception:
        main = list(config.DEFAULT_VOICES)
    extra = [v for v in _extra_list() if v not in main]
    return sorted(main) + sorted(extra)


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
