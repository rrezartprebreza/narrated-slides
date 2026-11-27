# cloner: your own voice (optional)

Clones a voice from a short English recording with [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Apache 2.0) and
serves it through the same OpenAI-style API as the other voice engines. Runs in Docker (CPU, `QWEN_MODEL` defaults to
the 0.6B model there) or natively on an Apple Silicon Mac with `scripts/run-cloner-mac.sh` (GPU, 1.7B model).

- `POST /voices` (multipart `name`, `consent=true`, `file`, optional `start` and `transcript`) stores a reference clip
  as voice `clone_<name>`. The transcript (what is said in the clip) lets Qwen3-TTS copy the voice more closely.
- `GET /voices`, `DELETE /voices/{id}` list and delete them. `GET /v1/audio/voices`, `POST /v1/audio/speech` speak.
- The model downloads on first start into `HF_HOME`; clips live in `VOICES_DIR`. CPU by default (`CLONE_DEVICE`).
- Unlike some cloning models, Qwen3-TTS does not watermark its output. Say that a narration is AI-generated
  where that matters.

Only clone your own voice or a voice you have permission to use.

Tests (no model needed): `pip install -r requirements.txt pytest && python -m pytest tests -q`
