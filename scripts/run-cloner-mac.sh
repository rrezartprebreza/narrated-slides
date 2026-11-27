#!/usr/bin/env bash
# Run the voice-cloning service natively on an Apple Silicon Mac, so it can use the GPU (Metal / MPS).
# Docker on macOS can't reach the GPU, so this is usually many times faster than the Docker version.
#
#   ./scripts/run-cloner-mac.sh          # first run installs everything (a few minutes), then starts it
#   CLONE_MODEL=qwen ./scripts/run-cloner-mac.sh start   # Qwen3-TTS: the most human-sounding engine (~4.5 GB model)
#   CLONE_MODEL=standard ...             # Chatterbox with the Emotion setting;  default: turbo (fastest)
#
# Then, in another terminal (once):
#   printf '\nCLONE_TTS_URL=http://host.docker.internal:8890\n' >> .env   (the leading \n matters)
#   docker compose stop cloner            # the Docker version is no longer needed
#   docker compose up -d narrator
#
# Keep this window open while you use your own voice (Ctrl+C stops it), or run it in the background:
#   ./scripts/run-cloner-mac.sh start     (also: stop, status, logs)
# It must listen on all interfaces (0.0.0.0) so the Docker containers can reach it. It has no password, so use it
# on a trusted network (home/office); macOS's firewall can block other devices. CLONE_HOST=127.0.0.1 to restrict it.
set -euo pipefail
cd "$(dirname "$0")/.."

# Background mode:  start | stop | status | logs   (no argument = run in this window)
PIDFILE="data/cloner/cloner.pid"
LOGFILE="data/cloner/cloner.log"
running() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }
port_pids() { lsof -ti tcp:8890 -sTCP:LISTEN 2>/dev/null | grep . ; }   # also finds one started in another window
case "${1:-}" in
  start)
    if running || port_pids >/dev/null; then
      now="$(curl -s http://127.0.0.1:8890/health | sed -n 's/.*"model":"\([a-z]*\)".*/\1/p')"
      if [[ -n "$now" && "$now" != "${CLONE_MODEL:-turbo}" ]]; then
        echo "Switching the voice service from $now to ${CLONE_MODEL:-turbo}..."
        "$0" stop
      else
        echo "Voice service already running${now:+ (model $now)}."; exit 0
      fi
    fi
    mkdir -p data/cloner
    nohup "$0" >"$LOGFILE" 2>&1 &   # a fresh log for each start
    echo $! >"$PIDFILE"
    echo "Voice service started in the background. It keeps running after you close Terminal."
    echo "Model: ${CLONE_MODEL:-turbo}. Check it:  $0 status     Follow the log:  $0 logs     Stop it:  $0 stop"
    exit 0 ;;
  stop)
    pids="$( { [[ -f "$PIDFILE" ]] && cat "$PIDFILE"; port_pids || true; } | sort -u | tr '\n' ' ')"
    rm -f "$PIDFILE"
    if [[ -z "${pids// /}" ]]; then echo "Voice service is not running."; exit 0; fi
    for p in $pids; do pkill -P "$p" 2>/dev/null || true; kill "$p" 2>/dev/null || true; done
    for _ in $(seq 1 20); do port_pids >/dev/null || break; sleep 0.5; done   # wait until the port is free
    for p in $(port_pids); do kill -9 "$p" 2>/dev/null || true; done
    echo "Voice service stopped."
    exit 0 ;;
  status)
    if running; then
      echo "Running (pid $(cat "$PIDFILE"))."
      curl -s http://127.0.0.1:8890/health && echo
    else echo "Not running. Start it with:  $0 start"; fi
    exit 0 ;;
  logs)
    exec tail -n 40 -f "$LOGFILE" ;;
esac

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

export CLONE_MODEL="${CLONE_MODEL:-turbo}"
if [[ "$CLONE_MODEL" == "qwen" ]]; then
  # Qwen3-TTS needs a different transformers version than Chatterbox, so it gets its own environment.
  VENV="cloner/.venv-mac-qwen"
  if [[ ! -x "$VENV/bin/uvicorn" ]] || ! "$VENV/bin/python" -c "import qwen_tts" >/dev/null 2>&1; then
    echo "Setting up Qwen3-TTS with $PY (first time only, a few minutes)..."
    "$PY" -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install fastapi "uvicorn[standard]" python-multipart qwen-tts==0.1.1
  fi
  command -v sox >/dev/null 2>&1 || echo "Tip: 'brew install sox' silences a harmless warning from Qwen3-TTS."
else
  VENV="cloner/.venv-mac"
  if [[ ! -x "$VENV/bin/uvicorn" ]]; then
    echo "Setting up the voice-cloning service with $PY (first time only, a few minutes)..."
    "$PY" -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -r cloner/requirements.txt chatterbox-tts==0.1.7
  fi
  # The watermark library (resemble-perth) imports pkg_resources, which comes from setuptools < 81.
  if ! "$VENV/bin/python" -c "import pkg_resources" >/dev/null 2>&1; then
    echo "Installing setuptools (needed by the watermark library)..."
    "$VENV/bin/pip" install "setuptools<81"
  fi
fi
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is needed:  brew install ffmpeg" >&2; exit 1; }

mkdir -p data/cloner/voices data/cloner/hf
export VOICES_DIR="$PWD/data/cloner/voices"
export HF_HOME="$PWD/data/cloner/hf"
export CLONE_DEVICE="${CLONE_DEVICE:-mps}"
export PYTORCH_ENABLE_MPS_FALLBACK=1   # run any operation the GPU lacks on the CPU instead of failing

echo "Voice cloning on the Mac GPU ($CLONE_DEVICE, model $CLONE_MODEL) at http://127.0.0.1:8890"
echo "Your voices are stored in data/cloner/voices. Keep this window open; Ctrl+C stops it."
cd cloner
exec "../$VENV/bin/uvicorn" app.main:app --host "${CLONE_HOST:-0.0.0.0}" --port 8890
