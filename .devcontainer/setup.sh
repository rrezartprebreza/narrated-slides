#!/usr/bin/env bash
# One-time setup in a codespace: create .env with Codespaces-friendly settings.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  {
    echo ""
    echo "# --- added by .devcontainer/setup.sh for GitHub Codespaces ---"
    echo "COMPOSE_PROFILES=ollama,clone"
    if [ -n "${CODESPACE_NAME:-}" ]; then
      echo "PRESENTON_PUBLIC_URL=https://${CODESPACE_NAME}-5001.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
    fi
  } >> .env
fi
