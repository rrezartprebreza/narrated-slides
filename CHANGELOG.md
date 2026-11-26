# Changelog

## v1.1.0 (2026-11-26)

- Albanian (Shqip) voice through a new local Piper service, downloaded on first start.
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
