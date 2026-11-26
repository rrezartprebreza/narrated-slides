# Configuration

Settings live in `.env` (copy `.env.example` to `.env`). After changing it, run `docker compose up -d` so the containers
pick the new values up.

## Everyday settings

| Variable | Default | Meaning |
|---|---|---|
| `NARRATOR_PORT` | `8000` | Port of the web app on your computer. |
| `PRESENTON_PORT` | `5001` | Port of Presenton. |
| `KOKORO_PORT` | `8880` | Port of the voice service. |
| `TTS_VOICE` | `af_heart` | Default voice. Users can change it in the app. |
| `MAX_UPLOAD_MB` | `100` | Largest `.pptx` accepted. |
| `RETENTION_DAYS` | `7` | Decks and videos older than this are deleted at startup. `0` keeps everything. |
| `KOKORO_IMAGE`, `PRESENTON_IMAGE` | tested version | Use a different image version. The defaults in `docker-compose.yml` are pinned to versions known to work. |

All ports are published on `127.0.0.1` only. To let other computers on your network use the app, change the `ports`
entry in `docker-compose.yml` to `"8000:8000"`. There is no login, so only do this on a network you trust.

## The AI note writer (optional)

Used by **Write with AI**. Any OpenAI-compatible chat API works.

| Variable | Default (in compose) | Meaning |
|---|---|---|
| `NOTES_LLM_BASE_URL` | `http://ollama:11434/v1` | API base URL. |
| `NOTES_LLM_MODEL` | `llama3.2:3b` | Model name. |
| `NOTES_LLM_API_KEY` | `not-needed` | Key, if the service needs one. |

**Local with Ollama in Docker:** `docker compose --profile ollama up -d`, then
`docker compose exec ollama ollama pull llama3.2:3b`.

**Ollama already installed on your Mac or PC:** set
`NOTES_LLM_BASE_URL=http://host.docker.internal:11434/v1` and pull your model with `ollama pull`.

**OpenAI:**

```
NOTES_LLM_BASE_URL=https://api.openai.com/v1
NOTES_LLM_MODEL=gpt-4.1-mini
NOTES_LLM_API_KEY=sk-...
```

Slide text is sent to the model you choose. With a hosted API that means it leaves your computer.

## Slide generation with Presenton (optional)

Presenton reads its own settings from `.env`:

```
LLM=ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
# or: LLM=openai and OPENAI_API_KEY=sk-...
# images: IMAGE_PROVIDER=pexels and PEXELS_API_KEY=...
# opt out of anonymous usage statistics: DISABLE_ANONYMOUS_TRACKING=true
```

To let this app generate decks (the *Generate one from an idea* panel), create an API key in Presenton
(http://localhost:5001), set `PRESENTON_API_KEY` in `.env`, and run `docker compose up -d`.
Without a key you can still build a deck in Presenton, export PPTX and upload it here.
See the [Presenton documentation](https://github.com/presenton/presenton) for all of its options.

## Voice engines

The app calls an OpenAI-compatible `POST {TTS_BASE_URL}/audio/speech` and, if available, `GET {TTS_BASE_URL}/audio/voices`.
Kokoro-FastAPI is the default. To use something else, set these on the `narrator` service in `docker-compose.yml`:

| Variable | Meaning |
|---|---|
| `TTS_BASE_URL` | e.g. `http://my-tts:8000/v1` |
| `TTS_MODEL` | Model name the server expects. |
| `TTS_VOICE` | Default voice. |
| `TTS_API_KEY` | Key, if needed. |
| `TTS_TIMEOUT_S` | Per-request timeout in seconds (default 300). |

## GPU (Linux or Windows with NVIDIA)

In `docker-compose.yml`, switch the Kokoro image to `ghcr.io/remsky/kokoro-fastapi-gpu` and uncomment its `deploy` block
(the same block exists for `ollama`). Docker Desktop on macOS cannot pass a GPU through; the CPU image is fine there.

## Other environment variables (narrator service)

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `/data` | Where decks are stored (a Docker volume by default). |
| `SOFFICE_CMD` | `soffice` | LibreOffice command. Only change in unusual environments. |
| `PRESENTON_URL` | `http://presenton:80` | How the narrator reaches Presenton inside Docker. |
| `PRESENTON_PUBLIC_URL` | `http://localhost:5001` | Link shown to users. |

## Backups and cleaning up

Decks live in the `narrator_data` volume. To wipe them: `docker compose down -v` (this also removes the Ollama models
volume). To free disk space from images: `docker image prune`.
