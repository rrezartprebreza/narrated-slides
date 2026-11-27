# Running in GitHub Codespaces

A codespace is a cloud machine with Docker. This repository includes a `.devcontainer/` setup, so the whole app starts
on its own: the voices (Kokoro and Albanian Piper), voice cloning, Ollama for notes and subtitle translation, and Presenton.

## Start

1. Open the repository on GitHub, click **Code**, then the **Codespaces** tab, then **⋯ → New with options**
   (or use the "Open in GitHub Codespaces" button in the README).
2. Pick **Machine type: 4-core, 16 GB RAM** or bigger, then **Create codespace**.
3. Wait. The first start builds the images and downloads several GB (voices, the cloning model, a small notes model).
   That takes 10 to 15 minutes. You can watch it in the terminal with `docker compose logs -f`.
4. Open the **PORTS** tab and click the globe icon next to **8000 (Narrated Slides)**. The app opens in a new browser tab.

Later starts are much faster, because the downloads are kept while the codespace exists.

## Using it

- Everything works as on your own computer, including **Record** in *My voice*: the page runs in your own browser,
  so it uses your microphone. Allow microphone access when the browser asks.
- Uploads and downloads go through the browser as usual.
- Port 8000 is private by default: only you, signed in to GitHub, can open it. Don't make it public.

## Costs and privacy

- Codespaces use your GitHub account's included monthly usage (core-hours and storage). A 4-core machine uses
  4 core-hours per hour. Check your remaining usage under GitHub **Settings → Billing**.
- **Stop** the codespace when you're done (Codespaces menu → *Stop current codespace*), or it keeps using hours until it
  times out. **Delete** it to free the storage.
- Your decks, recordings and videos live on GitHub's servers while the codespace exists. Delete the codespace to remove them.

## Troubleshooting

- **`docker: command not found`:** the codespace started in recovery mode (its setup failed). Press **F1**, run
  **Codespaces: Rebuild Container**, and wait. If it happens again, run **Codespaces: View Creation Log** and look for the error.

- **Page doesn't open / 502:** the app is still starting. Run `docker compose ps` in the terminal and wait until
  `narrator` is `healthy`.
- **"Voice cloning" stays amber:** the cloning model is still downloading. `docker compose logs -f cloner` prints
  `model ready` when done.
- **AI notes / translations unavailable:** the notes model downloads in the background on first start.
  Check `cat /tmp/ollama-pull.log`, or run `docker compose exec ollama ollama pull llama3.2:3b`.
- **Running out of memory:** pick an 8-core / 32 GB machine, or stop Presenton: `docker compose stop presenton`.
