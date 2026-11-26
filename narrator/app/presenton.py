"""Optional: generate a deck with a self-hosted Presenton instance and download the PPTX.

Uses Presenton's documented endpoint POST /api/v1/ppt/presentation/generate. The response
carries `path` (relative to the server root) which is downloaded to get the exported file.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from . import config


class PresentonError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.PRESENTON_API_KEY}"} if config.PRESENTON_API_KEY else {}


def healthy() -> bool:
    try:
        return httpx.get(config.PRESENTON_URL, timeout=3).status_code < 500
    except Exception:
        return False


def generate_pptx(
    dest: Path,
    prompt: str,
    n_slides: int | None = None,
    tone: str = "default",
    verbosity: str = "standard",
    template: str = "general",
) -> None:
    body: dict = {
        "content": prompt,
        "tone": tone,
        "verbosity": verbosity,
        "language": "English",
        "template": template,
        "include_title_slide": True,
        "export_as": "pptx",
    }
    if n_slides:
        body["n_slides"] = n_slides
    try:
        resp = httpx.post(
            f"{config.PRESENTON_URL}/api/v1/ppt/presentation/generate",
            json=body,
            headers=_headers(),
            timeout=httpx.Timeout(900, connect=10),  # LLM generation is slow
        )
    except httpx.HTTPError as exc:
        raise PresentonError(f"Could not reach Presenton at {config.PRESENTON_URL}: {exc}") from exc
    if resp.status_code in (401, 403):
        raise PresentonError(
            "Presenton rejected the request (unauthorised). Create an API key in Presenton "
            "and put it in PRESENTON_API_KEY."
        )
    if resp.status_code >= 400:
        raise PresentonError(f"Presenton error {resp.status_code}: {resp.text[:300]}")
    path = resp.json().get("path")
    if not path:
        raise PresentonError("Presenton did not return a file path.")
    url = path if path.startswith("http") else f"{config.PRESENTON_URL}/{path.lstrip('/')}"
    try:
        dl = httpx.get(url, headers=_headers(), timeout=120, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise PresentonError(f"Could not download the generated deck: {exc}") from exc
    if dl.status_code >= 400 or not dl.content:
        raise PresentonError(f"Could not download the generated deck ({dl.status_code}) from {url}")
    dest.write_bytes(dl.content)
