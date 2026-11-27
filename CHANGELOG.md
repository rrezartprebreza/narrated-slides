# Changelog

## v1.5.0 (2026-11-27)

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
