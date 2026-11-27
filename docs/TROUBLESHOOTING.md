# Troubleshooting

First look at the status pill at the top right of the app and open it: it lists each service and what to do.

Useful commands (run in the project folder):

```bash
docker compose ps                  # what is running
docker compose logs narrator       # the web app
docker compose logs kokoro         # the voice
docker compose logs presenton      # slide generation
docker compose up -d --build       # apply changes
```

## `env file .../.env not found`

You skipped the copy step, or the file has a stray dot (`.env.`). Run `cp .env.example .env` (check the name with `ls -a`).

## Port is already allocated / the page shows a different app

Another program uses port 8000. Add `NARRATOR_PORT=8010` to `.env`, run `docker compose up -d`, and open http://localhost:8010.
The same works for `PRESENTON_PORT` and `KOKORO_PORT`.

## "Voice offline" (red)

Kokoro is not answering.

- On the very first start it downloads its model. Wait a minute or two and look at `docker compose logs kokoro`.
- Run `docker compose ps`. If `kokoro` is not "running", `docker compose up -d kokoro`.
- If a new image version misbehaves, set `KOKORO_IMAGE` in `.env` to another version.

## No Albanian (Shqip) voices in the list

The `piper` service downloads the Albanian voice on first start. Wait a minute, then reload the page. Check:

```bash
docker compose ps piper
docker compose logs piper
```

If the download keeps failing (for example behind a company proxy), download a voice's `.onnx` and `.onnx.json` files (for example `edon/sq_AL-edon-medium.onnx`)
yourself and point `PIPER_VOICES` at a server you control, or copy them into the `piper_models` volume as `sq_edon.onnx` and
`sq_edon.onnx.json`.

## Export fails with "stopped while speaking" or "Connection reset by peer"

The voice service was killed mid-export, almost always because Docker ran out of memory. The cloning model alone needs
several GB, and Ollama, Presenton and Kokoro need their own.

- Docker Desktop, **Settings, Resources, Memory**: raise it to 12 GB or more (keep a few GB free for macOS), then **Apply & restart**.
- Or stop what you don't need while exporting: `docker compose stop ollama presenton`.
- Check the total in Docker Desktop's **Containers** page ("Container memory usage").

## My voice: "add-on isn't started", or the cloned voice is slow

- Start it: `docker compose --profile clone up -d --build`, then wait for the model download (several minutes the first time).
  Check progress with `docker compose logs -f cloner`; it prints `model ready` when done.
- The browser asks for microphone access the first time you press **Record**. If you blocked it, allow it in the
  address bar, or upload a clip instead.
- Bad clone quality is almost always the recording: use a quiet room, no music, one speaker, 10 to 20 seconds,
  close to the microphone (a headset or AirPods mic is often better than the laptop mic). Record again after updating:
  new recordings are cleaned automatically.
- Too slow: keep the default `CLONE_MODEL=turbo`. Docker on a Mac can't use the Apple GPU, so cloning runs on the CPU.
- Cloning runs on the CPU. Keep notes short, use 720p, or give Docker Desktop more CPUs.

## "Notes AI" is amber or red

Amber means it is not set up, which is fine: only **Write with AI** needs it. To enable it see
[Configuration](CONFIGURATION.md#the-ai-note-writer-optional). Red means it is configured but not answering:

- Ollama in Docker: `docker compose --profile ollama up -d`, then `docker compose exec ollama ollama pull <model>`.
- Ollama on your computer: use `http://host.docker.internal:11434/v1` and make sure `ollama serve` is running.
- Small models write uneven notes. Try a larger one, and always read what it wrote.

## Presenton is red, or generating a deck fails

- It is only needed for *Generate one from an idea*. Uploading decks works without it.
- "Create an API key": open http://localhost:5001, create a key, put it in `PRESENTON_API_KEY` in `.env`, run `docker compose up -d`.
- Generation can take several minutes with a local model.

## The upload fails

- Only `.pptx` is accepted. Save `.ppt`, Keynote and Google Slides decks as PowerPoint first.
- Files are limited to 100 MB (`MAX_UPLOAD_MB`).
- "The file is not a valid .pptx" usually means a renamed or damaged file. Open and re-save it in PowerPoint.

## Slides look different from PowerPoint

Slides are rendered with LibreOffice. Missing fonts are replaced, and some effects are not supported. Use common fonts, avoid
heavy effects, or export the slide as a picture inside PowerPoint.

## The video has no sound on some slides

A slide with empty notes is silent by design. Check the filmstrip: a grey circle means no notes.

## Export is slow

Text-to-speech on a CPU is the slow part. Use 720p, shorter notes, or the GPU image (see
[Configuration](CONFIGURATION.md#gpu-linux-or-windows-with-nvidia)). Giving Docker Desktop more CPUs and memory
(Settings, Resources) also helps.

## "Unknown job (the app may have restarted)"

The app restarted while a job was running. Your decks are kept; open it from *Your recent decks* and export again.

## Start over

```bash
docker compose down        # keeps your decks
docker compose down -v     # also deletes decks and downloaded models
```
