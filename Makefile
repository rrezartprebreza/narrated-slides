.PHONY: up down logs test screenshots

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
