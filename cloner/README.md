# cloner: your own voice (optional)

Clones a voice from a short English recording with [Chatterbox](https://github.com/resemble-ai/chatterbox) (MIT) and
serves it through the same OpenAI-style API as the other voice engines.

- `POST /voices` (multipart `name`, `consent=true`, `file`) stores a reference clip as voice `clone_<name>`.
- `GET /voices`, `DELETE /voices/{id}` list and delete them. `GET /v1/audio/voices`, `POST /v1/audio/speech` speak.
- The model (~2 GB) downloads on first start into `/models`; clips live in `/voices`. CPU by default (`CLONE_DEVICE`).
- Chatterbox watermarks its output so it can be identified as AI-generated.

Only clone your own voice or a voice you have permission to use.

Tests (no model needed): `pip install -r requirements.txt pytest && python -m pytest tests -q`
