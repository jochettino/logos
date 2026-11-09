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
    mode_catalogs = {mode: game.catalog_for_mode(catalog, mode) for mode in game.MODES}

    def session_catalog(session) -> dict[str, game.Item]:
        """Items of the mode the player picked (empty if they have not picked one)."""
        return mode_catalogs.get(session.get("mode"), {})

    def start_game(session, mode: str) -> None:
        """Begin a fresh game in the given mode. Best scores survive; everything else resets."""
        bests = dict(session.get("bests", {}))
        previous = session.get("mode", "classic")  # cookies from before modes were classic games
        bests[previous] = max(bests.get(previous, 0), session.get("score", 0))
        bests["classic"] = max(bests.get("classic", 0), session.pop("best", 0))
        session["bests"] = bests
        for key in ("attempts", "result", "over"):
            session.pop(key, None)
        session["mode"] = mode
        session["score"] = 0
        session["current"], session["seen"] = game.pick_next(mode_catalogs[mode], [])

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
        return templates.TemplateResponse(request, "modes.html", {"modes": game.MODES})

    @app.get("/game")
    def play_game(request: Request):
        session = request.session
        mode = session.get("mode")
        if mode not in game.MODES:
            return RedirectResponse("/play", status_code=303)
        catalog = mode_catalogs[mode]
        if not catalog:
            return templates.TemplateResponse(request, "game.html", {"empty": True})
        if "seen" not in session:
            start_game(session, mode)
        elif not session.get("over") and session.get("current") not in catalog:
            session["current"], session["seen"] = game.pick_next(catalog, session["seen"])
            if session["current"] is None:
                session["over"] = "won"
        score = session.get("score", 0)
        context = {
            "empty": False,
            "mode": mode,
            "mode_label": game.MODES[mode].label,
            "over": session.get("over"),
            "image_id": session.get("current"),
            "score": score,
            "best": max(session.get("bests", {}).get(mode, 0), score),
            "total": len(catalog),
            "result": session.pop("result", None),  # shown once, then cleared
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
        if mode not in game.MODES:
            return RedirectResponse("/play", status_code=303)
        start_game(request.session, mode)
        return RedirectResponse("/game", status_code=303)

    @app.get("/image/{image_id}")
    def image(request: Request, image_id: str):
        item = session_catalog(request.session).get(image_id)
        if item is None:
            raise HTTPException(status_code=404)
        media_type = mimetypes.guess_type(item.path.name)[0] or "application/octet-stream"
        return FileResponse(item.path, media_type=media_type)

    return app


app = create_app()
