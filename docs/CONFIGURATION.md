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

## Notes AI on a Mac (optional)

The notes AI drafts notes for slides that have none and translates subtitles. It is optional: without it you write the
notes yourself (or keep the ones already in your .pptx), and everything else works.

On an Apple Silicon Mac, run Ollama natively instead of in Docker. It uses the GPU, so it is faster, and Docker needs
much less memory (6 GB is enough in Docker Desktop → Settings → Resources):

```bash
brew install ollama
./scripts/run-ollama-mac.sh start      # also: stop, status, logs
docker compose stop ollama && docker compose up -d
```

`start` runs `ollama serve` on 0.0.0.0:11434 (so Docker can reach it), pulls `OLLAMA_MODEL` (default `llama3.2:3b`),
points `NOTES_LLM_BASE_URL` and `OLLAMA_URL` in `.env` at `host.docker.internal`, and removes `ollama` from
`COMPOSE_PROFILES`. If the Ollama menu-bar app is already running, quit it first: it only listens on 127.0.0.1.
`./scripts/run-ollama-mac.sh docker` switches back to Ollama in Docker.

## Voice cloning (optional)

The `cloner` service runs [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Apache 2.0) and clones a voice from a short
reference clip.

**Apple Silicon Macs (M1 to M4), recommended.** Docker can't use the Mac's GPU, so run the service natively instead
(needs `brew install python@3.12 ffmpeg`):

```bash
./scripts/run-cloner-mac.sh start      # also: stop, status, logs
printf '\nCLONE_TTS_URL=http://host.docker.internal:8890\n' >> .env   # once; the leading \n matters
docker compose up -d narrator
```

The first start installs Qwen3-TTS into `cloner/.venv-mac-qwen` and downloads `Qwen/Qwen3-TTS-12Hz-1.7B-Base` (about
4.5 GB) into `data/cloner/hf`. Voices are kept in `data/cloner/voices`. The service listens on port 8890 on all
interfaces so Docker can reach it, without a password: use it on a trusted network.
If you used the older Chatterbox engine, `./scripts/run-cloner-mac.sh cleanup` deletes what it left behind (about 5 GB).

**Other machines (and Codespaces)** use the Docker add-on in the `clone` profile:

```bash
docker compose --profile clone up -d --build
```

It runs on the CPU, so it uses the smaller `Qwen/Qwen3-TTS-12Hz-0.6B-Base` model (about 2.5 GB, in the
`cloner_models` volume) and is several times slower than the built-in voices. With an NVIDIA GPU, set
`CLONE_DEVICE=cuda`, give the service GPU access, and you can use the 1.7B model. To always start it, add
`COMPOSE_PROFILES=ollama,clone` (or just `clone`) to `.env`.

- Reference clips can be audio or video files (up to 100 MB); only the audio is kept, converted to mono 24 kHz, cleaned
  (low rumble removed, light noise reduction, level evened out) and cut to 20 seconds from the chosen start point.
- **What is said in the clip:** Qwen3-TTS copies a voice much more closely when it knows the words. Recordings made in
  the app fill this in with the sample text; for uploads, type it in. Clips cut at 20 seconds skip it, because the
  words would no longer match. Without it the voice's timbre is still copied, less closely.
- Each voice is analysed once and reused for every sentence; saved voices are analysed when the service starts.
- The copied voice keeps the tone of the recording, so record in the mood you want. The **Delivery** setting
  (`style` in the speech API: `steady`, `natural`, `expressive`) changes the sampling temperature, i.e. how freely
  the delivery varies.
- It speaks English (`QWEN_LANGUAGE`). Qwen3-TTS also supports Chinese, Japanese, Korean, German, French, Russian,
  Portuguese, Spanish and Italian, but not Albanian.

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
