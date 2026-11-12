# Logos

[![Vercel status](https://img.shields.io/website?url=https%3A%2F%2Flogos-the-game.vercel.app&up_message=OK&down_message=KO&up_color=brightgreen&down_color=red&label=Vercel)](https://logos-the-game.vercel.app) [![Build status](https://img.shields.io/github/actions/workflow/status/joshferatu/logos/ci.yml?branch=main&label=Build)](https://github.com/joshferatu/logos/actions/workflows/ci.yml)

A small logo-guessing game. The server shows an image from a brand or product; the player types its name. A correct guess scores a point and shows the next image; a wrong guess ends the game. Name every logo to win. The best score is remembered.

See [docs/how-to-play.md](docs/how-to-play.md) for the rules.

**Mobile-first:** Logos is designed for phones first and scaled up to larger screens, so layout, touch targets and performance on small screens take priority in any change.

## Tech stack

- **Python 3.12** (Vercel's default; pinned in `.python-version`, the code works on newer versions too)
- **FastAPI** for the server, **Jinja2** for server-rendered HTML
- Plain HTML and a small CSS file. Every guess is a form POST followed by a redirect (full page reload), so JavaScript is only used to focus the answer field on desktop.
- **pytest** + **httpx2** for tests, **uv** for environments and dependencies
- Deployed on **Vercel**

## Structure

```
app/
  main.py          FastAPI app factory and routes
  game.py          Pure game logic (catalog loading, answer matching, image picking)
  catalog/         One JSON file per category (game mode), plus catalog/images/
                   with the image files
  templates/       Jinja2 templates
  static/          CSS
tests/             pytest suite
docs/              Player-facing docs
```

### How it works

- State (score, best score, images already seen, current image, game-over state) lives in a **signed session cookie**. There is no database and the server keeps no state, which suits Vercel's serverless model.
- Images are served from `/image/{id}` using opaque ids derived from the filename hash, so the page source never reveals the answer. Answers stay on the server.
- Routes: `GET /` (menu), `GET /play` (choose a category), `GET /game`, `POST /guess`, `POST /new`, `GET /image/{id}`.
- The category files in `app/catalog/` define the game modes: their file name prefix sets the menu order, `title` and `description` fill the buttons, and `logos` lists the images.

## Adding images

See [docs/adding-images.md](docs/adding-images.md) for how to add logos to the game.

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
SECRET_KEY=dev uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Without `SECRET_KEY` a random one is generated and sessions reset on each restart.

## Run the tests

```bash
uv run pytest
```

## Deploy to Vercel

1. Push the repo and import it in Vercel. The FastAPI entrypoint is declared in `pyproject.toml` (`[tool.vercel] entrypoint = "app.main:app"`), and dependencies come from `pyproject.toml` / `uv.lock`. The Python version comes from `.python-version` (3.12).
2. Set the `SECRET_KEY` environment variable (see `.env.example`). The app refuses to start on Vercel without it, because every serverless instance must share the same key.
3. Deploy, then check that images load. Vercel bundles all project files by default, so `app/images/` ships with the function; confirm on the first deploy.

## Roadmap

- Add JavaScript to submit guesses without full reloads.
- More images (target: up to ~100).
