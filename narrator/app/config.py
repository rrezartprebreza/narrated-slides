"""Runtime configuration, read once from environment variables."""
import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


DATA_DIR = Path(_env("DATA_DIR", "/data"))

# Text-to-speech: any OpenAI-compatible /audio/speech endpoint (Kokoro-FastAPI by default)
TTS_BASE_URL = _env("TTS_BASE_URL", "http://kokoro:8880/v1").rstrip("/")
TTS_MODEL = _env("TTS_MODEL", "kokoro")
TTS_VOICE = _env("TTS_VOICE", "af_heart")
TTS_API_KEY = _env("TTS_API_KEY", "not-needed")

# Optional second engine for voices the main one lacks (Piper with Albanian by default).
# Voices it lists are routed to it automatically.
EXTRA_TTS_BASE_URL = _env("EXTRA_TTS_BASE_URL", "").rstrip("/")
EXTRA_TTS_MODEL = _env("EXTRA_TTS_MODEL", "piper")

# Optional voice-cloning service (Chatterbox). Its voices are named clone_<name>.
CLONE_TTS_URL = _env("CLONE_TTS_URL", "").rstrip("/")

# Optional: an OpenAI-compatible chat endpoint used to write missing speaker notes
# (Ollama exposes one at http://<host>:11434/v1)
NOTES_LLM_BASE_URL = _env("NOTES_LLM_BASE_URL", "").rstrip("/")
NOTES_LLM_MODEL = _env("NOTES_LLM_MODEL", "")
NOTES_LLM_API_KEY = _env("NOTES_LLM_API_KEY", "not-needed")

# Optional: Presenton, used to generate a deck from a prompt
PRESENTON_URL = _env("PRESENTON_URL", "http://presenton:80").rstrip("/")
PRESENTON_PUBLIC_URL = _env("PRESENTON_PUBLIC_URL", "http://localhost:5001").rstrip("/")
PRESENTON_API_KEY = _env("PRESENTON_API_KEY", "")

# LibreOffice command (split like a shell line); override only for sandboxes
SOFFICE_CMD = _env("SOFFICE_CMD", "soffice")

MAX_UPLOAD_MB = int(_env("MAX_UPLOAD_MB", "100"))
RETENTION_DAYS = int(_env("RETENTION_DAYS", "7"))
TTS_TIMEOUT_S = int(_env("TTS_TIMEOUT_S", "300"))

DEFAULT_VOICES = ["af_heart", "af_bella", "af_sky", "am_michael", "bf_emma"]
