#!/usr/bin/env bash
# One-time: create the GitHub repo, push, add topics and publish the v1.0.0 release.
# Needs the GitHub CLI logged in as you:  brew install gh && gh auth login
#   ./scripts/publish-github.sh
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="${REPO:-narrated-slides}"
OWNER="$(gh api user --jq .login)"
echo "Publishing as $OWNER/$REPO"

# 1. Pin the Kokoro and Presenton versions you tested (skipped if Docker isn't running)
if docker info >/dev/null 2>&1; then
  ./scripts/pin-images.sh || echo "(pinning skipped)"
fi

# 2. Commit everything under your own name
if [ ! -d .git ]; then git init -q -b main; fi
git add -A
git -c user.name="$(git config user.name || echo "$OWNER")" commit -qm "Narrated Slides v1.0.0" || echo "(nothing new to commit)"

# 3. Create the repo (or reuse it) and push
if ! gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  gh repo create "$OWNER/$REPO" --public \
    --description "Turn a PowerPoint deck into a narrated MP4 video with a free AI voice. Private, runs locally with Docker." \
    --source . --remote origin --push
else
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main
fi

# 4. Topics so people can find it
gh repo edit "$OWNER/$REPO" --homepage "https://github.com/$OWNER/$REPO" \
  --add-topic text-to-speech --add-topic tts --add-topic powerpoint --add-topic pptx \
  --add-topic video-generation --add-topic docker --add-topic self-hosted --add-topic kokoro \
  --add-topic presentation --add-topic accessibility --add-topic education --add-topic fastapi

# 5. Release with the demo video and sample deck attached
if ! gh release view v1.0.0 -R "$OWNER/$REPO" >/dev/null 2>&1; then
  cp narrator/app/assets/sample-deck.pptx /tmp/narrated-slides-sample.pptx
  gh release create v1.0.0 -R "$OWNER/$REPO" --title "Narrated Slides v1.0.0" --notes-file CHANGELOG.md \
    docs/demo.mp4 /tmp/narrated-slides-sample.pptx
fi

echo
echo "Done: https://github.com/$OWNER/$REPO"
echo "Check the Actions tab: CI should turn green in a few minutes."
