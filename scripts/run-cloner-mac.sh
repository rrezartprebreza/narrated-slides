#!/usr/bin/env bash
# Run the voice-cloning service natively on an Apple Silicon Mac, so it can use the GPU (Metal / MPS).
# Docker on macOS can't reach the GPU, so this is usually many times faster than the Docker version.
#
#   ./scripts/run-cloner-mac.sh          # first run installs everything (a few minutes), then starts it
#
# Then, in another terminal (once):
#   echo "CLONE_TTS_URL=http://host.docker.internal:8890" >> .env
#   docker compose stop cloner            # the Docker version is no longer needed
#   docker compose up -d narrator
#
# Keep this window open while you use your own voice. Press Ctrl+C to stop.
# It listens on 127.0.0.1 only. If the app cannot reach it, run with CLONE_HOST=0.0.0.0 (then it is visible on your network).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This script is for Apple Silicon Macs (M1/M2/M3/M4). Use the Docker 'clone' profile elsewhere." >&2
  exit 1
fi

PY=""
for candidate in python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "Python 3.10 to 3.12 is needed. Install it with:  brew install python@3.12" >&2
  exit 1
fi

VENV="cloner/.venv-mac"
if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "Setting up the voice-cloning service with $PY (first time only, a few minutes)..."
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r cloner/requirements.txt chatterbox-tts==0.1.7
fi
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is needed:  brew install ffmpeg" >&2; exit 1; }

mkdir -p data/cloner/voices data/cloner/hf
export VOICES_DIR="$PWD/data/cloner/voices"
export HF_HOME="$PWD/data/cloner/hf"
export CLONE_DEVICE="${CLONE_DEVICE:-mps}"
export CLONE_MODEL="${CLONE_MODEL:-turbo}"
export PYTORCH_ENABLE_MPS_FALLBACK=1   # run any operation the GPU lacks on the CPU instead of failing

echo "Voice cloning on the Mac GPU ($CLONE_DEVICE, model $CLONE_MODEL) at http://127.0.0.1:8890"
echo "Your voices are stored in data/cloner/voices. Keep this window open; Ctrl+C stops it."
cd cloner
exec "../$VENV/bin/uvicorn" app.main:app --host "${CLONE_HOST:-127.0.0.1}" --port 8890
