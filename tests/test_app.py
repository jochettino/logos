import json
import re

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


@pytest.fixture
def multi(tmp_path):
    entries = []
    for name in ("Alpha", "Beta"):
        (tmp_path / f"{name}.png").write_bytes(b"\x89PNG")
        entries.append({"file": f"{name}.png", "answer": name})
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps(entries))
    client = TestClient(create_app(tmp_path, manifest, secret_key="test"))
    client.catalog = game.load_catalog(tmp_path, manifest)
    return client


def answer_of(client):
    """Answer of the image currently shown (test-only peek into the catalog)."""
    return client.catalog[image_id(client.get("/").text)].answer


def image_id(html: str) -> str:
    return html.split("/image/")[1].split('"')[0]


def status(html: str) -> tuple[int, int]:
    """(score, best) as shown in the header pills."""
    return (
        int(re.search(r"Score <b>(\d+)</b>", html).group(1)),
        int(re.search(r"Best <b>(\d+)</b>", html).group(1)),
    )


def play(client, text):
    page = client.get("/").text
    return client.post("/guess", data={"image_id": image_id(page), "guess": text}).text


def test_landing_shows_image_and_zero_score(client):
    page = client.get("/").text
    assert "/image/" in page and status(page) == (0, 0)


def test_head_request_succeeds_for_uptime_checks(client):
    response = client.head("/")
    assert response.status_code == 200
    assert response.content == b""


def test_page_never_contains_the_answer(client):
    assert "Java" not in client.get("/").text


def test_blank_guess_is_ignored(client):
    page = play(client, "   ")
    assert "Type a guess first" in page and "Game over" not in page and "/image/" in page


def test_stale_form_is_ignored(client):
    client.get("/")
    page = client.post("/guess", data={"image_id": "stale", "guess": "Java"}).text
    assert status(page) == (0, 0) and "/image/" in page


def test_correct_guess_continues_to_next_logo(multi):
    page = play(multi, f" {answer_of(multi).lower()} ")
    assert "Correct!" in page and status(page) == (1, 1) and "/image/" in page


def test_wrong_guess_ends_game_without_revealing_answer(multi):
    answer = answer_of(multi)
    page = play(multi, "nope")
    assert "Oh, no!" in page and "Your streak ends here" in page and "Game over" in page and "Play again" in page and "/image/" not in page
    assert answer not in page and "The answer was" not in page


def test_guess_after_game_over_is_ignored(multi):
    page = multi.get("/").text
    item = image_id(page)
    play(multi, "nope")
    page = multi.post("/guess", data={"image_id": item, "guess": "Alpha"}).text
    assert "Game over" in page and status(page)[0] == 0


def test_answer_is_not_stored_in_cookie_after_loss(multi):
    answer = answer_of(multi)
    play(multi, "nope")
    assert answer not in multi.cookies.get("session", "")


def test_no_dramatic_message_while_playing_or_on_win(multi):
    assert "Oh, no!" not in multi.get("/").text
    page = ""
    for _ in range(2):
        page = play(multi, answer_of(multi))
    assert "Oh, no!" not in page


def test_naming_every_logo_wins(multi):
    page = ""
    for _ in range(2):
        page = play(multi, answer_of(multi))
    assert "You won!" in page and status(page) == (2, 2) and "/image/" not in page


def test_best_score_survives_a_new_game(multi):
    play(multi, answer_of(multi))
    play(multi, "nope")
    page = multi.post("/new").text
    assert status(page) == (0, 1) and "/image/" in page


def test_best_score_only_grows(multi):
    play(multi, answer_of(multi))
    play(multi, "nope")
    multi.post("/new")
    play(multi, "nope")
    assert status(multi.get("/").text)[1] == 1


def test_new_game_mid_game_restarts_keeping_best(multi):
    play(multi, answer_of(multi))
    page = multi.post("/new").text
    assert status(page) == (0, 1) and "Game over" not in page


def test_legacy_cookie_starts_fresh_and_keeps_score_as_best(client):
    from itsdangerous import TimestampSigner
    import base64

    data = base64.b64encode(json.dumps({"score": 5, "attempts": 9, "seen": [], "current": "x"}).encode())
    client.cookies.set("session", TimestampSigner("test").sign(data).decode())
    assert status(client.get("/").text) == (0, 5)


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
