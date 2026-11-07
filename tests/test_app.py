import json

import pytest
from fastapi.testclient import TestClient

from app import game
from app.main import create_app


@pytest.fixture
def images(tmp_path):
    (tmp_path / "only.png").write_bytes(b"\x89PNG")
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps([{"file": "only.png", "answer": "Java", "aliases": ["Java cup"]}]))
    return tmp_path, manifest


@pytest.fixture
def client(images):
    directory, manifest = images
    return TestClient(create_app(directory, manifest, secret_key="test"))


def image_id(html: str) -> str:
    return html.split("/image/")[1].split('"')[0]


def play(client, text):
    page = client.get("/").text
    return client.post("/guess", data={"image_id": image_id(page), "guess": text}).text


def test_landing_shows_image_and_zero_score(client):
    page = client.get("/").text
    assert "/image/" in page and "Score: 0 / 0" in page


def test_head_request_succeeds_for_uptime_checks(client):
    response = client.head("/")
    assert response.status_code == 200
    assert response.content == b""


def test_page_never_contains_the_answer(client):
    assert "Java" not in client.get("/").text


def test_correct_guess_scores(client):
    page = play(client, " java ")
    assert "Correct!" in page and "Score: 1 / 1" in page


def test_wrong_guess_reveals_answer_without_scoring(client):
    page = play(client, "Jvaa")
    assert "The answer was Java" in page and "Score: 0 / 1" in page


def test_blank_guess_is_not_counted(client):
    page = play(client, "   ")
    assert "Type a guess first" in page and "Score: 0 / 0" in page


def test_stale_form_is_ignored(client):
    client.get("/")
    page = client.post("/guess", data={"image_id": "stale", "guess": "Java"}).text
    assert "Score: 0 / 0" in page


def test_reset_clears_score(client):
    play(client, "Java")
    page = client.post("/reset").text
    assert "Score: 0 / 0" in page


def test_image_is_served_and_unknown_id_404s(client):
    item_id = image_id(client.get("/").text)
    assert client.get(f"/image/{item_id}").content == b"\x89PNG"
    assert client.get("/image/nope").status_code == 404


def test_empty_catalog_shows_friendly_message(tmp_path):
    app = create_app(tmp_path, tmp_path / "missing.json", secret_key="test")
    assert "No images configured" in TestClient(app).get("/").text


def test_bundled_sample_catalog_is_valid():
    from app.main import IMAGES_DIR, MANIFEST
    assert len(game.load_catalog(IMAGES_DIR, MANIFEST)) >= 1
