# Narrated Slides

[![CI](https://github.com/rrezartprebreza/narrated-slides/actions/workflows/ci.yml/badge.svg)](https://github.com/rrezartprebreza/narrated-slides/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Docker](https://img.shields.io/badge/runs%20with-Docker-2496ED?logo=docker&logoColor=white)
![Self-hosted](https://img.shields.io/badge/self--hosted-100%25%20local-6d4aff)

**Turn a PowerPoint deck into a narrated MP4 video.** Your speaker notes are read aloud by a natural-sounding AI voice
(or your own cloned voice), and you get the video, subtitles in up to six languages, per-slide audio and an updated deck. Everything runs on your own computer with Docker.
No account, no cloud, no per-minute fees.

<p align="center">
  <img src="docs/images/demo.gif" alt="Demo: open the sample deck, edit the script, export a narrated video" width="860">
</p>

## Who is it for?

- **Teachers and lecturers** turning lecture slides into videos with captions for students.
- **Teams** sharing onboarding, training or product updates people can watch any time.
- **Anyone** who wants the same clear delivery every time, without recording their own voice.

## Features

- **Upload a `.pptx`** or generate one from a prompt with [Presenton](https://github.com/presenton/presenton).
- **Slide-by-slide script editor.** Large preview, filmstrip, autosave, word count and spoken-length estimate.
- **Hear it before you commit.** Preview the voice for any slide.
- **Optional AI note writer** for slides that have no notes (local [Ollama](https://ollama.com) or any OpenAI-compatible API).
- **Free voices** from [Kokoro](https://github.com/remsky/Kokoro-FastAPI), or any OpenAI-compatible text-to-speech server.
- **Your own voice.** Record about 10 seconds in the browser and narrate in your own (English) voice, using the
  optional [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) voice-cloning add-on (fastest on an Apple Silicon Mac's GPU).
- **Subtitles in 6 languages** (English, Albanian, Italian, Portuguese, Norwegian, Turkish), translated by your AI model,
  added as selectable tracks in the MP4 and as SRT files.
- **Albanian (Shqip) voice** built in, through a local [Piper](https://github.com/OHF-Voice/piper1-gpl) engine. Add more Piper voices for other languages.
- **Four downloads:** MP4 video, SRT subtitles, a ZIP of MP3s (one per slide), and your deck with the final notes written in.
- **Private by design.** Services listen on `127.0.0.1` only; files stay in a Docker volume and are deleted after 7 days.
- Light and dark theme, keyboard shortcuts, and a one-click sample deck to try it.

<p align="center">
  <img src="docs/images/01-home.png" alt="Home screen" width="49%">
  <img src="docs/images/02-script.png" alt="Script editor" width="49%">
</p>
<p align="center">
  <img src="docs/images/03-export.png" alt="Voice, My voice and subtitle languages" width="49%">
  <img src="docs/images/04-result.png" alt="Finished video and downloads" width="49%">
</p>

## Run it in the cloud (GitHub Codespaces)

No Docker on your computer, or not enough memory? Open it in a codespace and everything starts by itself:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/rrezartprebreza/narrated-slides?quickstart=1)

Choose a **4-core / 16 GB** machine (or bigger). The first start downloads several GB, so give it 10 to 15 minutes, then
open the **PORTS** tab and click the globe next to port **8000**. Recording your voice works there too, because the page
runs in your own browser. Codespaces use your GitHub free monthly hours, and your files are on GitHub's servers while
the codespace exists. Stop the codespace when you're done. Details: [docs/CODESPACES.md](docs/CODESPACES.md).

## Quick start

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with the Compose plugin).

```bash
git clone https://github.com/rrezartprebreza/narrated-slides.git
cd narrated-slides
cp .env.example .env
docker compose up -d --build
```

Open **http://localhost:8000** and press **Try the sample deck**.

The first start downloads a few GB of images, and the voice service takes a minute to warm up. The status pill at the
top right turns green ("Ready") when the voice is available.

> **Port 8000 already used?** Add `NARRATOR_PORT=8010` to `.env`, run `docker compose up -d`, and open http://localhost:8010.

Want the AI note writer and local slide generation too? Start the optional Ollama container and download a small model:

```bash
docker compose --profile ollama up -d --build
docker compose exec ollama ollama pull llama3.2:3b
```

Want to narrate in your own voice? On an Apple Silicon Mac, run the voice-cloning service on the Mac's GPU (the first
start downloads about 4.5 GB):

```bash
./scripts/run-cloner-mac.sh start
printf '\nCLONE_TTS_URL=http://host.docker.internal:8890\n' >> .env
docker compose up -d narrator
```

On other machines use the Docker add-on instead (CPU, slower): `docker compose --profile clone up -d --build`.

Then open **Voice & export → My voice**, record yourself reading the sample text, and save.

## How it works

```mermaid
flowchart LR
    A[PPTX upload<br/>or Presenton] --> B[Narrator app]
    B -->|LibreOffice → PDF → images| C[Slide pictures]
    B -->|speaker notes| D[Kokoro TTS]
    B -->|Albanian notes| P[Piper TTS]
    P -->|MP3 per slide| F
    B -.->|optional: missing notes| E[Ollama / OpenAI-compatible LLM]
    C --> F[FFmpeg]
    D -->|MP3 per slide| F
    F --> G[MP4 + SRT + MP3s + deck with notes]
```

1. **Add a deck.** Hidden slides are skipped. Each visible slide's speaker notes become its script.
2. **Edit the script.** Changes save automatically. Slides without notes stay silent for a few seconds.
3. **Export.** Pick a voice and speed. Each slide is spoken, paired with its picture, then joined into one video.

More detail: [User guide](docs/USER_GUIDE.md) · [Configuration](docs/CONFIGURATION.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Architecture](docs/ARCHITECTURE.md)

## Documentation

| | |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Step by step for people using the app, including how to change a slide's look |
| [docs/CODESPACES.md](docs/CODESPACES.md) | Run it in the cloud with GitHub Codespaces |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every setting, GPU, other voice engines, using OpenAI instead of Ollama |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Red status lights, port conflicts, slow first start, odd-looking slides |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | For contributors: components, API, data layout |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Run it without Docker, tests, ideas |

## Good to know

- **Languages.** Kokoro covers English, Spanish, French, Italian, Portuguese, Hindi, Japanese and Chinese. Albanian comes from
  Piper. Other languages can be added as Piper voices (see [Configuration](docs/CONFIGURATION.md#albanian-and-other-piper-voices)).
- **Slide look.** Slides are rendered with LibreOffice, so unusual fonts or effects may look slightly different from
  PowerPoint. Slide text is not changed by the narration, so you can fix the design in PowerPoint and upload again.
- **Speed.** Speech is generated on your CPU, so export takes a while. Try the sample deck to see how long it takes on your machine.
- **Security.** There is no login: it is meant for one person on their own machine. Do not expose the ports to the internet.

## Project layout

```
narrator/          the web app (FastAPI + plain HTML/CSS/JS) and its tests
docker-compose.yml narrator + Kokoro + Presenton (+ optional Ollama)
docs/              guides and screenshots
scripts/           screenshots, demo GIF, image pinning, GitHub publish
```

## Credits

Built on the shoulders of [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) and
[Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI), [Presenton](https://github.com/presenton/presenton),
[Ollama](https://ollama.com), [FFmpeg](https://ffmpeg.org), [LibreOffice](https://www.libreoffice.org) and
[python-pptx](https://github.com/scanny/python-pptx). Their licenses apply to their own software.

## License

[MIT](LICENSE), except the `piper/` service, which is GPL-3.0-or-later because it uses the GPL-licensed Piper library
(see [piper/README.md](piper/README.md)).
