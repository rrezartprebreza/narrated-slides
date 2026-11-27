#!/usr/bin/env bash
# Runs every time the codespace starts: build and start all services, and pull a small notes model once.
set -uo pipefail
cd "$(dirname "$0")/.."
# Only one copy at a time (the automatic start and a manual run can overlap).
exec 9>/tmp/narrated-slides-start.lock
if ! flock -n 9; then
  echo "Already starting in another terminal. Check progress with: docker compose ps"
  exit 0
fi
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker compose up -d --build
( for i in $(seq 1 60); do
    docker compose exec -T ollama ollama list >/dev/null 2>&1 && break; sleep 5
  done
  docker compose exec -T ollama ollama list | grep -q "llama3.2:3b" || docker compose exec -T ollama ollama pull llama3.2:3b
) > /tmp/ollama-pull.log 2>&1 &
echo
echo "Narrated Slides is starting. Open the PORTS tab and click the globe next to port 8000."
echo "First start downloads several GB (voices, cloning model, notes model): give it 10-15 minutes."
echo "Progress: docker compose logs -f"
