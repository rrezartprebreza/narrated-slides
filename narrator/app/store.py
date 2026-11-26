"""On-disk storage for decks: /data/decks/<id>/{source.pptx, slides/, out/, state.json}."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import config

_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_lock = threading.Lock()


class DeckNotFound(KeyError):
    pass


def root() -> Path:
    path = config.DATA_DIR / "decks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def deck_dir(deck_id: str) -> Path:
    if not _ID_RE.match(deck_id):
        raise DeckNotFound(deck_id)
    return root() / deck_id


def new_deck() -> tuple[str, Path]:
    deck_id = uuid.uuid4().hex
    path = deck_dir(deck_id)
    path.mkdir(parents=True)
    return deck_id, path


def discard(deck_id: str) -> None:
    shutil.rmtree(deck_dir(deck_id), ignore_errors=True)


def load(deck_id: str) -> dict:
    state_file = deck_dir(deck_id) / "state.json"
    if not state_file.exists():
        raise DeckNotFound(deck_id)
    with _lock:
        return json.loads(state_file.read_text(encoding="utf-8"))


def save(deck_id: str, state: dict) -> None:
    state_file = deck_dir(deck_id) / "state.json"
    tmp = state_file.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, state_file)


def cleanup_old() -> int:
    """Delete decks not touched for RETENTION_DAYS. Returns how many were removed."""
    if config.RETENTION_DAYS <= 0:
        return 0
    cutoff = time.time() - config.RETENTION_DAYS * 86400
    removed = 0
    for path in root().iterdir():
        if not path.is_dir() or not _ID_RE.match(path.name):
            continue
        marker = path / "state.json"
        mtime = (marker if marker.exists() else path).stat().st_mtime
        if mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def list_decks() -> list[dict]:
    """Summaries of stored decks, most recently touched first."""
    items = []
    for path in root().iterdir():
        state_file = path / "state.json"
        if not path.is_dir() or not _ID_RE.match(path.name) or not state_file.exists():
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items.append({
            "id": path.name,
            "name": state.get("name", "Untitled"),
            "slides": len(state.get("slides", [])),
            "rendered": bool(state.get("outputs")),
            "updated": state_file.stat().st_mtime,
        })
    items.sort(key=lambda i: i["updated"], reverse=True)
    return items
