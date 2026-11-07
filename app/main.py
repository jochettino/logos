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

    @app.get("/")
    def index(request: Request):
        session = request.session
        if not catalog:
            return templates.TemplateResponse(request, "index.html", {"empty": True})
        if session.get("current") not in catalog:
            session["current"], session["seen"] = game.pick_next(
                catalog, session.get("seen", [])
            )
        context = {
            "empty": False,
            "image_id": session["current"],
            "score": session.get("score", 0),
            "attempts": session.get("attempts", 0),
            "result": session.pop("result", None),  # shown once, then cleared
        }
        return templates.TemplateResponse(request, "index.html", context)

    @app.post("/guess")
    def guess(request: Request, image_id: Annotated[str, Form()], guess: Annotated[str, Form()] = ""):
        session = request.session
        current = catalog.get(session.get("current", ""))
        # Ignore stale forms (back button, double submit) and blank guesses.
        if current is None or image_id != current.id:
            return RedirectResponse("/", status_code=303)
        if not guess.strip():
            session["result"] = {"kind": "blank"}
            return RedirectResponse("/", status_code=303)

        correct = game.is_correct(current, guess)
        session["attempts"] = session.get("attempts", 0) + 1
        if correct:
            session["score"] = session.get("score", 0) + 1
        session["result"] = {"kind": "correct" if correct else "wrong", "answer": current.answer}
        session["current"], session["seen"] = game.pick_next(
            catalog, session.get("seen", [])
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/reset")
    def reset(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    @app.get("/image/{image_id}")
    def image(image_id: str):
        item = catalog.get(image_id)
        if item is None:
            raise HTTPException(status_code=404)
        media_type = mimetypes.guess_type(item.path.name)[0] or "application/octet-stream"
        return FileResponse(item.path, media_type=media_type)

    return app


app = create_app()
