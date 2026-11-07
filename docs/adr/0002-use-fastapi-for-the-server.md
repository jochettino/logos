# 0002. Use FastAPI for the server

- Status: Accepted
- Date: 2026-11-07

## Context
- The game needs a small Python web server that renders HTML, handles form posts and serves images. It will be deployed on Vercel.
- The frontend starts as server-rendered HTML with full page reloads. JavaScript may be added later to reduce server calls, which could mean JSON endpoints next to the HTML routes.
- The maintainer is familiar with FastAPI and barely remembers Flask or Django.
- Vercel documents FastAPI as a supported framework: it detects an `app` instance at a known entrypoint and reads dependencies and configuration from `pyproject.toml`.
- Per-player state is kept in a signed session cookie (see `CLAUDE.md`), which Starlette, the layer FastAPI is built on, supports through `SessionMiddleware`.

## Decision
We will use FastAPI, with Jinja2 for templates and Uvicorn to run it locally.

- Familiarity: the maintainer already knows it, so work starts quickly and the code stays easy to maintain.
- Deployment: Vercel has a documented FastAPI path, so deployment follows supported guidance instead of custom setup.
- Growth: if JavaScript is added later, JSON endpoints can sit beside the HTML routes without changing framework.

## Alternatives Considered
- **Flask**: a comparable fit for a server-rendered app, and Vercel supports it too. Not chosen because the maintainer is not familiar with it. No benchmark or detailed feature comparison was done.
- **Django**: Vercel supports it, but it is a larger framework with its own project structure, ORM and admin. It brings more than a stateless game with no database needs. Not chosen for that reason and for unfamiliarity.
- **Other frameworks (Starlette alone, Litestar, etc.)**: not evaluated.

## Consequences
- Positive: fast start, a documented Vercel deployment path, and room to add JSON endpoints later.
- Positive: automatic OpenAPI docs and Pydantic validation are available if the app grows an API.
- Negative: today's app uses almost none of FastAPI's headline strengths (async handling, Pydantic models, generated API docs). Flask would have served the current scope about as well.
- Negative: the framework choice was driven mainly by familiarity, not a comparison. Switching later would mean rewriting `app/main.py`. `app/game.py` has no FastAPI imports by design, so the game logic would not change.
- Negative: Vercel's FastAPI entrypoint detection looks for an `app` instance. It is not confirmed that our `app = create_app()` factory pattern is always detected. The first deploy worked, so it is fine today.
