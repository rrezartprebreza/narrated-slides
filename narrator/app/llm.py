"""Optional: write speaker notes for slides that have none, using any OpenAI-compatible chat API."""
from __future__ import annotations

import re

import httpx

from . import config

SYSTEM_PROMPT = (
    "You write spoken narration for presentation slides. "
    "Write in plain, natural language as if a presenter is speaking to an audience. "
    "Always write in the same language as the slide content (for example, Albanian slides get Albanian narration). "
    "No markdown, no bullet points, no emoji, no stage directions, no slide numbers. "
    "Do not read the slide word for word; explain and connect the ideas. "
    "Write out symbols and abbreviations the way they are spoken."
)


def configured() -> bool:
    return bool(config.NOTES_LLM_BASE_URL and config.NOTES_LLM_MODEL)


def healthy() -> bool:
    if not configured():
        return False
    try:
        r = httpx.get(
            f"{config.NOTES_LLM_BASE_URL}/models",
            headers={"Authorization": f"Bearer {config.NOTES_LLM_API_KEY}"},
            timeout=3,
        )
        return r.status_code < 500
    except Exception:
        return False


def _tidy(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(narration|script|notes?)\s*:\s*", "", text, flags=re.I)
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    text = text.strip().strip('"').strip()
    return re.sub(r"\s*\n+\s*", " ", text)


def write_notes(deck_title: str, slide: dict, total: int, sentences: int = 3) -> str:
    if not configured():
        raise RuntimeError("No notes LLM is configured (set NOTES_LLM_BASE_URL and NOTES_LLM_MODEL).")
    content = slide["title"] or "(no title)"
    if slide["text"]:
        content += "\n" + slide["text"]
    user = (
        f"Deck: {deck_title or 'Untitled'}\n"
        f"This is slide {slide['n']} of {total}.\n\n"
        f"Slide content:\n{content}\n\n"
        f"Write the narration for this slide in {sentences} to {sentences + 1} sentences."
    )
    resp = httpx.post(
        f"{config.NOTES_LLM_BASE_URL}/chat/completions",
        json={
            "model": config.NOTES_LLM_MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
            "temperature": 0.5,
            "stream": False,
        },
        headers={"Authorization": f"Bearer {config.NOTES_LLM_API_KEY}"},
        timeout=300,
    )
    resp.raise_for_status()
    text = _tidy(resp.json()["choices"][0]["message"]["content"])
    if not text:
        raise RuntimeError("The model returned an empty answer.")
    return text
