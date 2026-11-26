.PHONY: up down logs test screenshots demo pin publish

up:            ## build and start everything
	docker compose up -d --build

down:          ## stop everything (your decks are kept)
	docker compose down

logs:          ## follow the narrator log
	docker compose logs -f narrator

test:          ## run the test-suite (needs ffmpeg, poppler and LibreOffice installed)
	cd narrator && python -m pytest tests -q

screenshots:   ## regenerate docs/images (also needs playwright)
	python scripts/make_screenshots.py

demo:          ## re-record docs/images/demo.gif
	python scripts/make_demo.py

pin:           ## pin Kokoro/Presenton to the versions you have running
	./scripts/pin-images.sh

publish:       ## create the GitHub repo, push, add topics, publish v1.0.0
	./scripts/publish-github.sh
