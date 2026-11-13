import mimetypes
import os
import secrets
import warnings
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import game

# Serve the PWA manifest with its registered type; some systems do not know .webmanifest.
mimetypes.add_type("application/manifest+json", ".webmanifest")

BASE_DIR = Path(__file__).parent
CATALOG_DIR = BASE_DIR / "catalog"

# /image/{id} ids hash the image bytes, so a given URL never changes its content.
IMAGE_CACHE = "public, max-age=31536000, immutable"


class AssetFiles(StaticFiles):
    """Static files with a short, revalidating cache lifetime.

    Asset names carry no content hash, so they cannot be marked immutable: a deploy that
    changes style.css must reach players in minutes, not a year.
    """

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if os.environ.get("VERCEL"):
        # Serverless instances must share the key or sessions break.
        raise RuntimeError("SECRET_KEY must be set in the Vercel project settings")
    warnings.warn("SECRET_KEY not set; using a random one (sessions reset on restart)")
    return secrets.token_urlsafe(32)


def create_app(
    catalog_dir: Path = CATALOG_DIR,
    secret_key: str | None = None,
) -> FastAPI:
    app = FastAPI(title="Logos")
    app.add_middleware(SessionMiddleware, secret_key=secret_key or _secret_key())
    app.mount("/static", AssetFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIR / "templates")
    categories = game.load_catalog(catalog_dir)
    by_id = {category.id: category for category in categories}

    def session_catalog(session) -> dict[str, game.Item]:
        """Items of the mode the player picked (empty if they have not picked one)."""
        category = by_id.get(session.get("mode"))
        return category.items if category else {}

    def start_game(session, mode: str) -> None:
        """Begin a fresh game in the given mode. Best scores survive; everything else resets."""
        bests = dict(session.get("bests", {}))
        previous = session.get("mode", "tech")  # cookies from before modes were tech games
        bests[previous] = max(bests.get(previous, 0), session.get("score", 0))
        bests["tech"] = max(bests.get("tech", 0), session.pop("best", 0))
        session["bests"] = bests
        for key in ("attempts", "result", "over"):
            session.pop(key, None)
        session["mode"] = mode
        session["score"] = 0
        session["current"], session["seen"] = game.pick_next(by_id[mode].items, [])

    # HEAD is allowed so uptime checks (e.g. the README status badge) get a 200.
    @app.api_route("/", methods=["GET", "HEAD"])
    def landing(request: Request):
        return templates.TemplateResponse(request, "landing.html")

    @app.get("/how-to-play")
    def how_to_play(request: Request):
        return templates.TemplateResponse(request, "how_to_play.html")

    @app.get("/about")
    def about(request: Request):
        return templates.TemplateResponse(request, "about.html")

    @app.get("/play")
    def choose_mode(request: Request):
        return templates.TemplateResponse(request, "modes.html", {"categories": categories})

    @app.get("/game")
    def play_game(request: Request):
        session = request.session
        mode = session.get("mode")
        if mode not in by_id:
            return RedirectResponse("/play", status_code=303)
        catalog = by_id[mode].items
        if not catalog:
            return templates.TemplateResponse(request, "game.html", {"empty": True})
        if "seen" not in session:
            start_game(session, mode)
        elif not session.get("over") and session.get("current") not in catalog:
            session["current"], session["seen"] = game.pick_next(catalog, session["seen"])
            if session["current"] is None:
                session["over"] = "won"
        score = session.get("score", 0)
        current = catalog.get(session.get("current") or "")
        context = {
            "empty": False,
            "mode": mode,
            "mode_label": by_id[mode].title,
            "over": session.get("over"),
            "image_id": session.get("current"),
            "photo": current.photo if current else False,
            "score": score,
            "best": max(session.get("bests", {}).get(mode, 0), score),
            "total": len(catalog),
            "result": session.pop("result", None),  # shown once, then cleared
            "share_url": str(request.url_for("landing")),
            "share_text": f"I scored {score} in {by_id[mode].title} at Logos 🎯 Can you beat me?",
        }
        return templates.TemplateResponse(request, "game.html", context)

    @app.post("/guess")
    def guess(request: Request, image_id: Annotated[str, Form()], guess: Annotated[str, Form()] = ""):
        session = request.session
        catalog = session_catalog(session)
        current = catalog.get(session.get("current") or "")
        # Ignore stale forms (back button, double submit), finished games and blank guesses.
        if session.get("over") or current is None or image_id != current.id:
            return RedirectResponse("/game", status_code=303)
        if not guess.strip():
            session["result"] = {"kind": "blank"}
            return RedirectResponse("/game", status_code=303)

        if not game.is_correct(current, guess):
            # Game over: the answer is deliberately not revealed or stored in the cookie.
            session["over"] = "lost"
            session["current"] = None
            return RedirectResponse("/game", status_code=303)

        session["score"] = session.get("score", 0) + 1
        bests = dict(session.get("bests", {}))
        bests[session["mode"]] = max(bests.get(session["mode"], 0), session["score"])
        session["bests"] = bests
        session["current"], session["seen"] = game.pick_next(catalog, session.get("seen", []))
        if session["current"] is None:
            session["over"] = "won"
        return RedirectResponse("/game", status_code=303)

    @app.post("/new")
    def new_game(request: Request, mode: Annotated[str, Form()] = ""):
        if mode not in by_id:
            return RedirectResponse("/play", status_code=303)
        start_game(request.session, mode)
        return RedirectResponse("/game", status_code=303)

    @app.get("/image/{image_id}")
    def image(request: Request, image_id: str):
        item = session_catalog(request.session).get(image_id)
        if item is None:
            raise HTTPException(status_code=404)
        media_type = mimetypes.guess_type(item.path.name)[0] or "application/octet-stream"
        return FileResponse(item.path, media_type=media_type, headers={"Cache-Control": IMAGE_CACHE})

    return app


app = create_app()
