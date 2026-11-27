FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models/hf VOICES_DIR=/voices

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 sox \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 app && mkdir -p /models /voices && chown app:app /models /voices

WORKDIR /srv
# CPU-only PyTorch keeps the image far smaller than the default CUDA build
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio
COPY requirements.txt .
RUN pip install -r requirements.txt qwen-tts==0.1.1
COPY app ./app
USER app
VOLUME ["/models", "/voices"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
