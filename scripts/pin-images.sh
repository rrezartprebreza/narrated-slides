#!/usr/bin/env bash
# Pin docker-compose.yml to the exact Kokoro and Presenton images you have running and tested.
# Run from the project folder after `docker compose up` works:  ./scripts/pin-images.sh
set -euo pipefail
cd "$(dirname "$0")/.."

pin() {  # $1 = variable name, $2 = image name
  local digest
  digest=$(docker image inspect "$2" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)
  if [[ -z "$digest" ]]; then
    echo "!! $2 is not pulled yet. Run 'docker compose pull' first." >&2
    return 1
  fi
  # Replace the default inside ${VAR:-...}
  python3 - "$1" "$digest" <<'PY'
import re, sys
var, digest = sys.argv[1], sys.argv[2]
p = "docker-compose.yml"
s = open(p).read()
s2 = re.sub(r"\$\{" + var + r":-[^}]+\}", "${" + var + ":-" + digest + "}", s)
open(p, "w").write(s2)
PY
  echo "pinned $1 -> $digest"
}

pin KOKORO_IMAGE ghcr.io/remsky/kokoro-fastapi-cpu:latest
pin PRESENTON_IMAGE ghcr.io/presenton/presenton:latest
echo "Done. Check with: git diff docker-compose.yml"
