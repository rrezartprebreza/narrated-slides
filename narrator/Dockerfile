FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

# ffmpeg: video; poppler: PDF -> images; LibreOffice: PPTX -> PDF; fonts: so slides render like PowerPoint
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg poppler-utils libreoffice-impress \
      fonts-liberation fonts-dejavu-core fonts-noto-core fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app:app /data

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
USER app
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/live', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
