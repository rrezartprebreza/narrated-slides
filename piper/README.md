# piper: extra voice engine (Albanian by default)

A small service that runs [Piper](https://github.com/OHF-Voice/piper1-gpl) text-to-speech behind the same OpenAI-style
API as Kokoro (`GET /v1/audio/voices`, `POST /v1/audio/speech`). Narrated Slides uses it for voices Kokoro does not have.

- Voices come from `PIPER_VOICES` (`name=URL-of-model.onnx`, comma separated) and are downloaded once into `/models`.
- Default: `sq_edon`, an Albanian voice by Edon Sekiraqa (`edonseki/folsh.ai` on Hugging Face). Check each voice's own license.
- `GET /health` answers 503 until at least one voice is loaded.

Tests (no model needed): `pip install -r requirements.txt pytest && python -m pytest tests -q`

## License

This folder is licensed **GPL-3.0-or-later** (see `COPYING`), because it uses the GPL-licensed `piper-tts` library.
It is a separate program that the main app talks to over HTTP; the rest of the repository stays under the MIT license.
