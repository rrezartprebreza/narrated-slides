"""Optional: write speaker notes for slides that have none, using any OpenAI-compatible chat API."""
from __future__ import annotations

import json
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


def write_notes(deck_title: str, slide: dict, total: int, sentences: int = 3, language: str | None = None) -> str:
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
    if language:
        user += (f" Write it in {language}, even if the slide is in another language. "
                 f"Use correct {language} spelling and letters, and write numbers out as words.")
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


TRANSLATE_PROMPT = (
    "You translate subtitles for a narrated presentation. "
    "Translate each line naturally and accurately, keeping the meaning and tone. "
    "Keep names, product names and numbers as they are. Keep each line short like a subtitle. "
    "Answer with a JSON array of strings only: one translated string per input line, same order, same count."
)


def _chat(system: str, user: str, temperature: float = 0.2) -> str:
    resp = httpx.post(
        f"{config.NOTES_LLM_BASE_URL}/chat/completions",
        json={
            "model": config.NOTES_LLM_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "stream": False,
        },
        headers={"Authorization": f"Bearer {config.NOTES_LLM_API_KEY}"},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_array(text: str, n: int) -> list[str] | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, list) or len(data) != n:
        return None
    out = [str(x).strip() for x in data]
    return out if all(out) else None


def translate_lines(lines: list[str], language: str, batch: int = 30) -> list[str]:
    """Translate subtitle lines into `language`, keeping the count and order."""
    if not configured():
        raise RuntimeError("Translating subtitles needs the notes AI (set NOTES_LLM_BASE_URL and NOTES_LLM_MODEL).")
    result: list[str] = []
    for i in range(0, len(lines), batch):
        chunk = lines[i:i + batch]
        user = f"Translate these {len(chunk)} subtitle lines into {language}:\n" + json.dumps(chunk, ensure_ascii=False)
        parsed = _parse_array(_chat(TRANSLATE_PROMPT, user), len(chunk))
        if parsed is None:  # model broke the format: fall back to one line at a time
            parsed = []
            for line in chunk:
                one = _parse_array(_chat(TRANSLATE_PROMPT, f"Translate this 1 subtitle line into {language}:\n"
                                         + json.dumps([line], ensure_ascii=False)), 1)
                if one is None:
                    raise RuntimeError(f"The model did not return a usable {language} translation.")
                parsed += one
        result += parsed
    return result
