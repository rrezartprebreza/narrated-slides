# Architecture

A small FastAPI application with a plain HTML/CSS/JS front end. No database, no build step, no message queue.

```
Browser ──HTTP──▶ narrator (FastAPI, port 8000)
                    ├─ LibreOffice (soffice, headless)  PPTX → PDF
                    ├─ pdftoppm (poppler)               PDF → slide-NNN.jpg
                    ├─ python-pptx                      read titles/notes, write notes back
                    ├─ FFmpeg                           still + audio → segment → concat → MP4
                    ├─ Kokoro (OpenAI-style /audio/speech)   text → MP3
                    ├─ optional LLM (OpenAI-style /chat/completions)   missing notes
                    └─ optional Presenton (/api/v1/ppt/presentation/generate)   prompt → PPTX
```

## Code map (`narrator/app/`)

| File | Responsibility |
|---|---|
| `main.py` | HTTP routes and request validation. Serves the UI. |
| `pipeline.py` | The long operations: prepare a deck, write notes, render the video. |
| `jobs.py` | In-process job runner (2 worker threads) with progress and user-facing error handling. |
| `store.py` | Deck storage on disk, listing, retention cleanup. |
| `pptx_tools.py` | Extract slides, skip hidden ones, render images, write notes back. |
| `tts.py`, `llm.py`, `presenton.py` | Clients for the external services. Retries and clear error messages. |
| `video.py` | FFmpeg helpers, subtitle cue splitting. |
| `config.py` | Environment variables, read once at startup. |
| `../../piper/` | Separate small service: Piper TTS behind the same OpenAI-style API, for Albanian and other Piper voices. |
| `static/` | `index.html`, `style.css`, `app.js`, `logo.svg`. |
| `assets/sample-deck.pptx` | The sample deck offered on the home page. |

## Flow

1. **Prepare** (`POST /api/decks`, `/api/decks/sample`, `/api/decks/generate`): a job reads the deck, converts it to PDF with
   LibreOffice, rasterises pages to JPEG, maps pages to visible slides (hidden slides are skipped), and writes `state.json`.
2. **Edit**: the browser autosaves notes with `PUT /api/decks/{id}/notes`. Optional `POST …/suggest-notes` runs a job.
3. **Render** (`POST …/render`): per slide, call TTS, probe the audio length, build a segment with FFmpeg (image + audio,
   or image + silence), then concatenate segments. Subtitles, the audio ZIP and the deck with notes are written alongside.
4. The UI polls `GET /api/jobs/{id}` once a second for progress.

## API

| Method and path | Purpose |
|---|---|
| `GET /api/health` | Service status, version, limits. |
| `GET /api/voices` | Available voices. |
| `POST /api/tts/preview` | Short MP3 for the “preview voice” buttons. |
| `POST /api/decks` | Upload a `.pptx` (multipart). Returns `job_id`, `deck_id`. |
| `POST /api/decks/sample` | Create a deck from the bundled sample. |
| `POST /api/decks/generate` | Generate a deck with Presenton. |
| `GET /api/decks` | Recent decks. |
| `GET/PATCH/DELETE /api/decks/{id}` | Read, rename, delete. |
| `PUT /api/decks/{id}/notes` | Save notes `{ "notes": {"1": "…"} }`. |
| `GET /api/decks/{id}/slides/{n}.jpg` | Slide picture. |
| `POST /api/decks/{id}/suggest-notes` | AI notes job. |
| `POST /api/decks/{id}/render` | Render job. |
| `GET /api/decks/{id}/files/{name}` | Download `narrated.mp4`, `narration.srt`, `narration-audio.zip`, `deck-with-notes.pptx` (`?inline=1` to play). |
| `GET /api/jobs/{id}` | `status` (`queued`, `running`, `done`, `error`), `progress` 0 to 1, `step`, `result`, `error`. |

Interactive API docs: http://localhost:8000/docs

## Data layout

```
/data/decks/<32-hex-id>/
  source.pptx      the original upload (never modified)
  slides/          slide-001.jpg …
  out/             narrated.mp4, narration.srt, narration-audio.zip, deck-with-notes.pptx
  state.json       name, slides (title, text, notes, image), settings, outputs
```

Decks untouched for `RETENTION_DAYS` are removed at startup.

## Design decisions

- **Jobs in memory.** Fine for one user on one machine. A restart forgets running jobs but not decks.
- **LibreOffice for rendering.** Free and scriptable; fidelity is good, not perfect. A per-call profile directory plus a lock keeps
  parallel conversions from clashing.
- **OpenAI-compatible interfaces** for speech and notes, so engines can be swapped through configuration.
- **Two voice engines.** Voices listed by `EXTRA_TTS_BASE_URL` (Piper) go there; everything else goes to Kokoro.
- **No authentication.** Intended to run on `localhost`. Do not expose it to the internet as is.
- **Non-root container**, ports bound to `127.0.0.1`.

## Tests

`narrator/tests/test_e2e.py` starts fake TTS, LLM and Presenton servers and drives the real pipeline (LibreOffice, poppler,
FFmpeg) through the HTTP API. `scripts/make_screenshots.py` also drives the real UI in headless Chromium.
