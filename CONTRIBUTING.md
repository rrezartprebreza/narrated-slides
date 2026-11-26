# Contributing

Thanks for helping! This is a small project, so the process is light.

## Run it locally without Docker

You need Python 3.11+, `ffmpeg`, `poppler-utils` (`pdftoppm`) and LibreOffice (`soffice`) on your PATH, and a text-to-speech
server (the quickest is `docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu`).

```bash
cd narrator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
DATA_DIR=./.data TTS_BASE_URL=http://localhost:8880/v1 uvicorn app.main:app --reload --port 8000
```

The UI is plain HTML, CSS and JavaScript in `narrator/app/static/`. There is no build step, so reload the page after editing.

## Tests

```bash
make test        # or: cd narrator && python -m pytest tests -q
```

The tests start tiny fake TTS, notes-LLM and Presenton servers, so they do not need Docker, Kokoro or Ollama. They do
need `ffmpeg`, `pdftoppm` and `soffice`, because the real rendering pipeline runs.

## Before you open a pull request

- Add or update a test for behaviour you change (`narrator/tests/test_e2e.py`).
- If you change the UI, run `make screenshots` and look at `docs/images/` to check nothing broke. Commit the new images
  only if the UI changed on purpose.
- Keep user-facing errors plain and actionable ("Kokoro isn't answering. Check `docker compose logs kokoro`"), not stack traces.
- Update `docs/` if you add a setting or change behaviour.

## Ideas that would be welcome

- More voice engines (a ready-made compose snippet for Piper or a cloud TTS).
- Per-slide voice or speed overrides.
- Slide transitions or a short intro/outro in the video.
- A translated UI.

## Reporting a bug

Open an issue and include what you did, what you expected, and the output of `docker compose ps` and
`docker compose logs narrator` (remove anything private).
