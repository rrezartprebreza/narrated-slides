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


def _root() -> str:
    base = config.TTS_BASE_URL
    return base[: -len("/v1")] if base.endswith("/v1") else base


def speech(text: str, voice: str | None = None, speed: float = 1.0, fmt: str = "mp3") -> bytes:
    text = clean_for_speech(text)
    if not text:
        raise TTSError("Nothing to say: the text is empty.")
    payload = {
        "model": config.TTS_MODEL,
        "input": text,
        "voice": voice or config.TTS_VOICE,
        "response_format": fmt,
        "speed": speed,
    }
    last: Exception | None = None
    # The TTS container can still be starting (first boot) - retry for ~1 minute.
    for attempt in range(6):
        try:
            resp = httpx.post(
                f"{config.TTS_BASE_URL}/audio/speech",
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
    raise TTSError(f"Could not reach the TTS server at {config.TTS_BASE_URL}: {last}")


def voices() -> list[str]:
    try:
        resp = httpx.get(f"{config.TTS_BASE_URL}/audio/voices", headers=_headers(), timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("voices", [])
        names = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("id") or item.get("name")
                if name:
                    names.append(str(name))
        if names:
            return sorted(names)
    except Exception:
        pass
    return list(config.DEFAULT_VOICES)


def healthy() -> bool:
    for url in (f"{_root()}/health", f"{config.TTS_BASE_URL}/audio/voices"):
        try:
            if httpx.get(url, headers=_headers(), timeout=3).status_code < 500:
                return True
        except Exception:
            continue
    return False
