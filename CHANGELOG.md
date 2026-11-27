# Changelog

## v1.8.1 (2026-11-27)

- `scripts/run-ollama-mac.sh`: run the notes AI natively on an Apple Silicon Mac (GPU) instead of in Docker, so Docker
  needs much less memory. It updates `.env` for you; `docker` switches back.
- The Services panel says you can write notes yourself when the notes AI is off.

## v1.8.0 (2026-11-27)

- Your own voice keeps the feeling you record it with: the recording guide now says so, and you can say your own words.
- New **Delivery** setting for your own voices: Steady, Natural or Expressive (how freely the voice varies its tone).

## v1.7.0 (2026-11-27)

- Qwen3-TTS is now the only voice-cloning engine; Chatterbox and the Emotion setting are removed.
  On an Apple Silicon Mac: `./scripts/run-cloner-mac.sh start` (Mac GPU, 1.7B model). The Docker add-on runs Qwen3-TTS
  on the CPU with the smaller 0.6B model (`QWEN_MODEL` to change). Saved voices keep working.
- `./scripts/run-cloner-mac.sh cleanup` deletes what Chatterbox left behind (about 5 GB). `stop` also stops a service
  started from another Terminal window.

## v1.6.0 (2026-11-27)

- Qwen3-TTS voice cloning, the most human-sounding engine: `CLONE_MODEL=qwen ./scripts/run-cloner-mac.sh start` on an
  Apple Silicon Mac (own environment, Mac GPU, about 4.5 GB model; `QWEN_MODEL` picks the smaller 0.6B model).
- My voices: a **What is said in the clip** box, filled in automatically for recordings, so Qwen3-TTS can copy the
  voice more closely. The Services panel shows which cloning engine is running.

## v1.5.0 (2026-11-27)

- `scripts/run-cloner-mac.sh`: run voice cloning natively on Apple Silicon to use the GPU (MPS); point the app at it
  with `CLONE_TTS_URL`.
- Faster previews in your own voice: only the opening sentences are previewed, and saved voices are analysed in
  advance (when saved and when the service starts), so the first preview doesn't wait.
- Much faster cloned voices: Chatterbox Turbo by default (`CLONE_MODEL=turbo`), and the voice sample is analysed once
  instead of for every sentence. `CLONE_MODEL=standard` keeps the slower, expressive model with Emotion.
- Saved voice samples are cleaned (rumble filter, noise reduction, even loudness) for a better clone.

## v1.4.1 (2026-11-27)

- Run in GitHub Codespaces: `.devcontainer/` starts every service automatically (needs a 16 GB machine).
- Clearer errors when a voice service runs out of memory, and when an uploaded clip has no sound.

## v1.4.0 (2026-11-27)

- Emotion for your own voices: Calm, Natural, Lively or Dramatic (Chatterbox expressiveness), in previews and exports.
- My voice accepts video files too (for example a saved reel), with a "Start at" field to skip music or an intro.

## v1.3.0 (2026-11-27)

- **My voice:** clone your own English voice from a 10 to 20 second recording, made in the browser or uploaded, with an
  explicit permission checkbox. Runs locally with Chatterbox as the optional `clone` profile.
- Cloned voices appear under "My voices" in every voice picker; manage or delete them in the My voice dialog.

## v1.2.0 (2026-11-27)

- Subtitles in English, Albanian, Italian, Portuguese, Norwegian and Turkish: translated by the notes AI, embedded as
  selectable tracks in the MP4, and downloadable as SRT files (ZIP). The in-page player shows every track.

## v1.1.0 (2026-11-26)

- Albanian (Shqip) voices (Arben, Arta, Dren, Edon) through a new local Piper service, downloaded on first start.
- Voices grouped by language, with a voice picker on the script page too.
- "Write with AI" writes in the slide's language.
- Links to Presenton from the services panel, the generate panel and errors.

## v1.0.0 (2026-11-26)

First public release.

- Upload a `.pptx`, or generate one from a prompt with Presenton.
- Slide-by-slide script editor with filmstrip, autosave, word count and spoken-length estimate.
- Voice preview per slide; optional AI note writer (Ollama or any OpenAI-compatible API).
- Export an MP4, SRT subtitles, one MP3 per slide, and the deck with final notes.
- One-click sample deck, recent decks, rename and delete.
- Light and dark theme, keyboard shortcuts, mobile layout.
- Docker Compose setup with Kokoro TTS, Presenton and optional Ollama, all bound to localhost.
