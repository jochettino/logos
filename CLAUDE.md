# CLAUDE.md

Logos: a logo-guessing game. FastAPI + Jinja2, no JavaScript yet, deployed on Vercel. Rules live in `docs/how-to-play.md`; setup in `README.md`.

## Commands

- Install: `uv sync` (dependencies live in `pyproject.toml`; `uv.lock` is committed)
- Run: `SECRET_KEY=dev uv run uvicorn app.main:app --reload`
- Test: `uv run pytest`

## Layout

- `app/game.py`: pure logic (catalog, matching, image picking). Keep it free of FastAPI imports.
- `app/main.py`: `create_app()` factory + routes. Module-level `app` is the Vercel entrypoint (`[tool.vercel] entrypoint` in `pyproject.toml`).
- `app/images.json` + `app/images/`: the catalog. Edit these to add images; steps are in `docs/adding-images.md`.
- `tests/`: `test_game.py` for logic, `test_app.py` for HTTP behavior via `TestClient`.

## Conventions and constraints

- **Stateless server.** All player state is in the signed session cookie (`score`, `best`, `seen`, `current`, `result`, `over`). No globals, files or DB for per-player data: Vercel instances don't share memory.
- **Never leak answers to the browser.** Images use opaque ids from `game.make_id`; templates must not render `answer` or `aliases`.
- Guess flow is POST -> 303 redirect -> GET (no resubmit on refresh). The form carries `image_id`; stale submissions are ignored.
- Matching: case-insensitive, whitespace-normalised exact match against the answer or aliases (`game.normalize`). No fuzzy matching, by design.
- A game is one pass through every image, each shown once. A wrong answer ends it (`over = "lost"`) without revealing or storing the answer; naming them all ends it with `"won"`. `best` survives new games. Cookies from the endless version (with `attempts`) restart fresh, keeping their score as `best`.
- **Mobile-first.** Design and test for small touch screens first, then enhance for wider ones. Write base CSS for phones and use `min-width` media queries for larger screens. Keep the viewport meta tag, use touch-friendly tap targets (about 44px) and readable text sizes, avoid hover-only interactions, and keep pages light.
- Keep the frontend plain HTML/CSS until JavaScript is deliberately introduced.
- `SECRET_KEY` is required when `VERCEL` is set. Never commit real keys; `.env` is gitignored.
- Add or change behavior with a test in the matching test file.
