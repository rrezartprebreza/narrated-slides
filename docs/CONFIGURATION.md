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

**Translated subtitles** use the same model. Larger models translate much better than `llama3.2:3b`, especially into
Albanian and Norwegian.

**Albanian notes.** When a Shqip voice is selected, **Write with AI** asks the model to write in Albanian. Small local
models such as `llama3.2:3b` write weak Albanian. A larger multilingual model (for example `gemma3:12b` or `qwen2.5:7b` in
Ollama, if your computer has the memory) or a hosted model such as `gpt-4.1-mini` usually does much better. Always read
the draft before exporting.

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

## Albanian and other Piper voices

Kokoro has no Albanian voice, so the `piper` service runs [Piper](https://github.com/OHF-Voice/piper1-gpl) with a community
Albanian voices (Arben, Arta, Dren and Edon, from `edonseki/folsh.ai` on Hugging Face). It downloads them (about 60 MB each) on
first start into the `piper_models` volume. The app lists its voices under **Shqip (Albanian)** and routes them to Piper
automatically.

Add or replace Piper voices in `.env` (name=URL of the `.onnx` file; the `.onnx.json` must sit next to it at the same URL + `.json`):

```
PIPER_VOICES=sq_arben=https://huggingface.co/edonseki/folsh.ai/resolve/main/arben/sq_AL-arben-medium.onnx,sq_arta=https://huggingface.co/edonseki/folsh.ai/resolve/main/arta/sq_AL-arta-medium.onnx,sq_dren=https://huggingface.co/edonseki/folsh.ai/resolve/main/dren/sq_AL-dren-medium.onnx,sq_edon=https://huggingface.co/edonseki/folsh.ai/resolve/main/edon/sq_AL-edon-medium.onnx,de_thorsten=https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
```

Then `docker compose up -d`. Check each voice's license before using it commercially: the Albanian voice's card says only
"Creative Commons" without naming the variant.

To turn the extra engine off, remove `EXTRA_TTS_BASE_URL` from the `narrator` service and the `piper` service from `docker-compose.yml`.

| Variable | Where | Meaning |
|---|---|---|
| `EXTRA_TTS_BASE_URL` | narrator | Second OpenAI-compatible TTS server. Its voices are routed to it. |
| `EXTRA_TTS_MODEL` | narrator | Model name sent to it (default `piper`). |
| `PIPER_VOICES` | piper | Voices to download and serve. |

## Voice cloning (optional)

The `cloner` service runs [Chatterbox](https://github.com/resemble-ai/chatterbox) (MIT) and clones a voice from a short
reference clip. It's in the `clone` profile, so it only starts when asked:

```bash
docker compose --profile clone up -d --build
```

- The first start downloads the model (about 2 GB) into the `cloner_models` volume. The Services panel shows
  "Starting" until it is loaded.
- Reference clips can be audio or video files (up to 100 MB); only the audio is kept, converted to mono 24 kHz and cut to
  20 seconds from the chosen start point. They are stored in the `cloner_voices` volume.
- `CLONE_MODEL=turbo` (default) uses Chatterbox Turbo: several times faster, natural tone, no Emotion control.
  `CLONE_MODEL=standard` is slower but supports the Emotion setting. Change it in `.env`, then
  `docker compose --profile clone up -d`. Each model downloads once.
- Your reference clip is analysed once and reused for every sentence, and it is cleaned when saved
  (low rumble removed, light noise reduction, level evened out).
- **Apple Silicon Macs (M1 to M4):** Docker can't use the Mac's GPU, so cloning in Docker runs on the CPU. For much
  faster cloning run it natively instead: `./scripts/run-cloner-mac.sh` (needs `brew install python@3.12 ffmpeg`),
  then add `CLONE_TTS_URL=http://host.docker.internal:8890` to `.env`, run `docker compose stop cloner` and
  `docker compose up -d narrator`. Record your voice again afterwards: the native service keeps voices in
  `data/cloner/voices`, separate from the Docker volume.
- Emotion presets (standard model only) map to Chatterbox's `exaggeration` / `cfg_weight`: Calm 0.3/0.5, Natural 0.5/0.5, Lively 0.8/0.35,
  Dramatic 1.2/0.3.
- It runs on the CPU by default (`CLONE_DEVICE=cpu`), which is slower than Kokoro: expect exports to take several times
  longer. On a Linux or Windows machine with an NVIDIA GPU, set `CLONE_DEVICE=cuda` and give the service GPU access.
- Chatterbox adds an inaudible watermark to everything it generates, so cloned speech can be identified as AI-made.
- To always start it, add `COMPOSE_PROFILES=ollama,clone` (or just `clone`) to `.env`.

| Variable | Where | Meaning |
|---|---|---|
| `CLONE_TTS_URL` | narrator | Address of the cloner (set in compose). Voices named `clone_*` are routed there. |
| `CLONE_DEVICE` | cloner | `cpu` (default) or `cuda`. |

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
