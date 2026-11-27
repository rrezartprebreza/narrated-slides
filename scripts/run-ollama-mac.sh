#!/usr/bin/env bash
# Run the notes AI (Ollama) natively on an Apple Silicon Mac instead of in Docker.
# On the Mac it uses the GPU, so it is faster, and Docker needs much less memory.
#
#   ./scripts/run-ollama-mac.sh start    # starts Ollama, downloads the model once, points the app at it
#   ./scripts/run-ollama-mac.sh stop | status | logs
#   ./scripts/run-ollama-mac.sh docker   # go back to Ollama in Docker
#
# Then restart the app once:  docker compose stop ollama && docker compose up -d
#
# The notes AI is optional: without it you write the slide notes yourself (or keep the ones in your .pptx).
# Ollama listens on all interfaces (0.0.0.0:11434) so the Docker containers can reach it; it has no password,
# so use it on a trusted network.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
PIDFILE="data/ollama/ollama.pid"
LOGFILE="data/ollama/ollama.log"
HOST_URL="http://host.docker.internal:11434"
up() { curl -s -o /dev/null -m 2 http://127.0.0.1:11434/api/version; }

set_env() {  # set_env KEY VALUE: replace the line in .env, or add it on its own line
  local key="$1" value="$2"
  touch .env
  if grep -q "^${key}=" .env; then
    KEY="$key" VALUE="$value" perl -pi -e 's/^\Q$ENV{KEY}\E=.*/$ENV{KEY}=$ENV{VALUE}/' .env
  else
    [[ -s .env && "$(tail -c1 .env)" != "" ]] && echo >> .env
    echo "${key}=${value}" >> .env
  fi
}

profiles_without_ollama() {
  local current
  current="$(sed -n 's/^COMPOSE_PROFILES=//p' .env | tail -1)"
  [[ -z "$current" ]] && return 0
  local kept
  kept="$(echo "$current" | tr ',' '\n' | grep -v '^ollama$' | paste -sd, - || true)"
  set_env COMPOSE_PROFILES "$kept"
}

case "${1:-}" in
  start)
    if ! command -v ollama >/dev/null 2>&1; then
      echo "Ollama is not installed. Install it with:  brew install ollama" >&2
      exit 1
    fi
    mkdir -p data/ollama
    if up; then
      echo "Ollama is already running."
      if ! lsof -iTCP:11434 -sTCP:LISTEN -n -P 2>/dev/null | grep -q '\*:11434'; then
        echo "Note: it only listens on this Mac (127.0.0.1), so Docker can't reach it." >&2
        echo "Quit the Ollama app (menu bar icon > Quit) or run 'brew services stop ollama', then run this again." >&2
        exit 1
      fi
    else
      OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve >"$LOGFILE" 2>&1 &
      echo $! >"$PIDFILE"
      for _ in $(seq 1 30); do up && break; sleep 1; done
      up || { echo "Ollama did not start. See $LOGFILE" >&2; exit 1; }
      echo "Ollama started on the Mac GPU. It keeps running after you close Terminal."
    fi
    echo "Getting the model $MODEL (downloads once, about 2 GB)..."
    ollama pull "$MODEL"
    set_env NOTES_LLM_BASE_URL "$HOST_URL/v1"
    set_env NOTES_LLM_MODEL "$MODEL"
    set_env OLLAMA_URL "$HOST_URL"
    set_env OLLAMA_MODEL "$MODEL"
    profiles_without_ollama
    echo
    echo "Done. .env now points the app at this Ollama. Restart the app once:"
    echo "  docker compose stop ollama && docker compose up -d"
    exit 0 ;;
  stop)
    if [[ -f "$PIDFILE" ]] && kill "$(cat "$PIDFILE")" 2>/dev/null; then echo "Ollama stopped."
    else echo "Ollama was not started by this script."; fi
    rm -f "$PIDFILE"
    exit 0 ;;
  status)
    if up; then echo "Ollama is running. Models:"; ollama list; else echo "Ollama is not running."; fi
    exit 0 ;;
  logs)
    exec tail -n 40 -f "$LOGFILE" ;;
  docker)
    set_env NOTES_LLM_BASE_URL "http://ollama:11434/v1"
    set_env OLLAMA_URL "http://ollama:11434"
    current="$(sed -n 's/^COMPOSE_PROFILES=//p' .env | tail -1)"
    echo "$current" | tr ',' '\n' | grep -qx ollama || set_env COMPOSE_PROFILES "${current:+$current,}ollama"
    echo "The app will use Ollama in Docker again:  docker compose up -d"
    exit 0 ;;
  *)
    echo "Usage: $0 start | stop | status | logs | docker" >&2
    exit 1 ;;
esac
