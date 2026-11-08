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

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
MANIFEST = BASE_DIR / "images.json"


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
    images_dir: Path = IMAGES_DIR,
    manifest: Path = MANIFEST,
    secret_key: str | None = None,
) -> FastAPI:
    app = FastAPI(title="Logos")
    app.add_middleware(SessionMiddleware, secret_key=secret_key or _secret_key())
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIR / "templates")
    catalog = game.load_catalog(images_dir, manifest)

    def start_game(session) -> None:
        """Begin a fresh game. The best score survives; everything else resets."""
        session["best"] = max(session.get("best", 0), session.get("score", 0))
        for key in ("attempts", "result", "over"):
            session.pop(key, None)
        session["score"] = 0
        session["current"], session["seen"] = game.pick_next(catalog, [])

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
    def play(request: Request):
        session = request.session
        if not catalog:
            return templates.TemplateResponse(request, "game.html", {"empty": True})
        # Cookies from the endless version have "attempts"; start fresh, keeping their score as best.
        if "seen" not in session or "attempts" in session:
            start_game(session)
        elif not session.get("over") and session.get("current") not in catalog:
            session["current"], session["seen"] = game.pick_next(catalog, session["seen"])
            if session["current"] is None:
                session["over"] = "won"
        context = {
            "empty": False,
            "over": session.get("over"),
            "image_id": session.get("current"),
            "score": session.get("score", 0),
            "best": max(session.get("best", 0), session.get("score", 0)),
            "total": len(catalog),
            "result": session.pop("result", None),  # shown once, then cleared
        }
        return templates.TemplateResponse(request, "game.html", context)

    @app.post("/guess")
    def guess(request: Request, image_id: Annotated[str, Form()], guess: Annotated[str, Form()] = ""):
        session = request.session
        current = catalog.get(session.get("current") or "")
        # Ignore stale forms (back button, double submit), finished games and blank guesses.
        if session.get("over") or current is None or image_id != current.id:
            return RedirectResponse("/play", status_code=303)
        if not guess.strip():
            session["result"] = {"kind": "blank"}
            return RedirectResponse("/play", status_code=303)

        if not game.is_correct(current, guess):
            # Game over: the answer is deliberately not revealed or stored in the cookie.
            session["over"] = "lost"
            session["current"] = None
            return RedirectResponse("/play", status_code=303)

        session["score"] = session.get("score", 0) + 1
        session["best"] = max(session.get("best", 0), session["score"])
        session["current"], session["seen"] = game.pick_next(catalog, session.get("seen", []))
        if session["current"] is None:
            session["over"] = "won"
        return RedirectResponse("/play", status_code=303)

    @app.post("/new")
    def new_game(request: Request):
        start_game(request.session)
        return RedirectResponse("/play", status_code=303)

    @app.get("/image/{image_id}")
    def image(image_id: str):
        item = catalog.get(image_id)
        if item is None:
            raise HTTPException(status_code=404)
        media_type = mimetypes.guess_type(item.path.name)[0] or "application/octet-stream"
        return FileResponse(item.path, media_type=media_type)

    return app


app = create_app()
