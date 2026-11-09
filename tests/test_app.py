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
    client = TestClient(create_app(directory, manifest, secret_key="test"))
    client.post("/new", data={"mode": "classic"})
    return client


@pytest.fixture
def multi(tmp_path):
    entries = []
    for name in ("Alpha", "Beta"):
        (tmp_path / f"{name}.png").write_bytes(b"\x89PNG")
        entries.append({"file": f"{name}.png", "answer": name})
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps(entries))
    client = TestClient(create_app(tmp_path, manifest, secret_key="test"))
    client.post("/new", data={"mode": "classic"})
    client.catalog = game.load_catalog(tmp_path, manifest)
    return client


def answer_of(client):
    """Answer of the image currently shown (test-only peek into the catalog)."""
    return client.catalog[image_id(client.get("/game").text)].answer


def image_id(html: str) -> str:
    return html.split("/image/")[1].split('"')[0]


def status(html: str) -> tuple[int, int]:
    """(score, best) as shown in the header pills."""
    return (
        int(re.search(r"Score <b>(\d+)</b>", html).group(1)),
        int(re.search(r"Best <b>(\d+)</b>", html).group(1)),
    )


def play(client, text):
    page = client.get("/game").text
    return client.post("/guess", data={"image_id": image_id(page), "guess": text}).text


def test_game_shows_image_and_zero_score(client):
    page = client.get("/game").text
    assert "/image/" in page and status(page) == (0, 0)


def test_landing_shows_menu_and_no_game(client):
    page = client.get("/").text
    assert "Logos" in page and "/play" in page and "/how-to-play" in page and "/about" in page
    assert "/image/" not in page


def test_menu_pages_render(client):
    assert "How to play" in client.get("/how-to-play").text
    assert "Main menu" in client.get("/about").text


def test_game_links_back_to_main_menu(client):
    page = client.get("/game").text
    assert "Main menu" in page and "New game" not in page


def test_playing_from_menu_starts_fresh_game_keeping_best(multi):
    play(multi, answer_of(multi))
    page = multi.post("/new", data={"mode": "classic"}).text
    assert status(page) == (0, 1)


def test_guess_field_is_focused_and_inside_a_submit_form(client):
    page = client.get("/game").text
    form = page.split('class="guess"')[1].split("</form>")[0]
    assert 'name="guess" autofocus' in form and 'type="submit"' in form


def test_head_request_succeeds_for_uptime_checks(client):
    response = client.head("/")
    assert response.status_code == 200
    assert response.content == b""


def test_page_never_contains_the_answer(client):
    assert "Java" not in client.get("/game").text


def test_blank_guess_is_ignored(client):
    page = play(client, "   ")
    assert "Type a guess first" in page and "Game over" not in page and "/image/" in page


def test_stale_form_is_ignored(client):
    client.get("/game")
    page = client.post("/guess", data={"image_id": "stale", "guess": "Java"}).text
    assert status(page) == (0, 0) and "/image/" in page


def test_correct_guess_continues_to_next_logo_without_banner(multi):
    page = play(multi, f" {answer_of(multi).lower()} ")
    assert "Correct!" not in page and status(page) == (1, 1) and "/image/" in page


def test_wrong_guess_ends_game_without_revealing_answer(multi):
    answer = answer_of(multi)
    page = play(multi, "nope")
    assert "Oh, no!" in page and "Your streak ends here" in page and "Game over" in page and "Play again" in page and "/image/" not in page
    assert answer not in page and "The answer was" not in page


def test_guess_after_game_over_is_ignored(multi):
    page = multi.get("/game").text
    item = image_id(page)
    play(multi, "nope")
    page = multi.post("/guess", data={"image_id": item, "guess": "Alpha"}).text
    assert "Game over" in page and status(page)[0] == 0


def test_answer_is_not_stored_in_cookie_after_loss(multi):
    answer = answer_of(multi)
    play(multi, "nope")
    assert answer not in multi.cookies.get("session", "")


def test_no_dramatic_message_while_playing_or_on_win(multi):
    assert "Oh, no!" not in multi.get("/game").text
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
    page = multi.post("/new", data={"mode": "classic"}).text
    assert status(page) == (0, 1) and "/image/" in page


def test_best_score_only_grows(multi):
    play(multi, answer_of(multi))
    play(multi, "nope")
    multi.post("/new", data={"mode": "classic"})
    play(multi, "nope")
    assert status(multi.get("/game").text)[1] == 1


def test_new_game_mid_game_restarts_keeping_best(multi):
    play(multi, answer_of(multi))
    page = multi.post("/new", data={"mode": "classic"}).text
    assert status(page) == (0, 1) and "Game over" not in page


def test_legacy_cookie_starts_fresh_and_keeps_score_as_best(client):
    from itsdangerous import TimestampSigner
    import base64

    data = base64.b64encode(json.dumps({"score": 5, "attempts": 9, "seen": [], "current": "x"}).encode())
    client.cookies.clear()
    client.cookies.set("session", TimestampSigner("test").sign(data).decode())
    client.post("/new", data={"mode": "classic"})
    assert status(client.get("/game").text) == (0, 5)


def test_image_is_served_and_unknown_id_404s(client):
    item_id = image_id(client.get("/game").text)
    assert client.get(f"/image/{item_id}").content == b"\x89PNG"
    assert client.get("/image/nope").status_code == 404


def test_empty_catalog_shows_friendly_message(tmp_path):
    app = create_app(tmp_path, tmp_path / "missing.json", secret_key="test")
    client = TestClient(app)
    client.post("/new", data={"mode": "classic"})
    assert "No images configured" in client.get("/game").text


def test_bundled_sample_catalog_is_valid():
    from app.main import IMAGES_DIR, MANIFEST
    assert len(game.load_catalog(IMAGES_DIR, MANIFEST)) >= 1


@pytest.fixture
def mixed(tmp_path):
    """One logo per category: tech, adult and uncategorised."""
    entries = []
    for name, category in (("Alpha", "tech"), ("Beta", "adult"), ("Gamma", None)):
        (tmp_path / f"{name}.png").write_bytes(b"\x89PNG")
        entries.append({"file": f"{name}.png", "answer": name, **({"category": category} if category else {})})
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps(entries))
    return TestClient(create_app(tmp_path, manifest, secret_key="test"))


def logos_in(client, mode):
    client.post("/new", data={"mode": mode})
    return int(re.search(r"Logo \d+ of (\d+)", client.get("/game").text).group(1))


def test_mode_screen_offers_both_games(client):
    page = client.get("/play").text
    assert "Classic" in page and "18+" in page and 'value="classic"' in page and 'value="18plus"' in page


def test_game_without_a_mode_redirects_to_mode_screen(mixed):
    response = mixed.get("/game", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/play"


def test_unknown_mode_is_rejected(mixed):
    response = mixed.post("/new", data={"mode": "nope"}, follow_redirects=False)
    assert response.headers["location"] == "/play"


def test_classic_has_tech_and_uncategorised_logos_only(mixed):
    assert logos_in(mixed, "classic") == 2


def test_18plus_adds_adult_logos(mixed):
    assert logos_in(mixed, "18plus") == 3


def test_classic_never_serves_adult_logos(mixed):
    adult = game.make_id("Beta.png")
    mixed.post("/new", data={"mode": "classic"})
    assert mixed.get(f"/image/{adult}").status_code == 404
    mixed.post("/new", data={"mode": "18plus"})
    assert mixed.get(f"/image/{adult}").status_code == 200


def test_play_again_keeps_the_mode(mixed):
    assert logos_in(mixed, "18plus") == 3
    mixed.post("/guess", data={"image_id": image_id(mixed.get("/game").text), "guess": "nope"})
    page = mixed.get("/game").text
    assert 'name="mode" value="18plus"' in page
    mixed.post("/new", data={"mode": "18plus"})
    assert "18+" in mixed.get("/game").text


def test_best_score_is_kept_per_mode(mixed):
    mixed.post("/new", data={"mode": "classic"})
    for _ in range(2):
        page = mixed.get("/game").text
        answer = next(n for n in ("Alpha", "Beta", "Gamma") if game.make_id(f"{n}.png") == image_id(page))
        mixed.post("/guess", data={"image_id": image_id(page), "guess": answer})
    assert status(mixed.get("/game").text) == (2, 2)
    mixed.post("/new", data={"mode": "18plus"})
    assert status(mixed.get("/game").text) == (0, 0)
    mixed.post("/new", data={"mode": "classic"})
    assert status(mixed.get("/game").text) == (0, 2)


def test_photo_entries_fill_the_card_and_logos_do_not(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "person.jpg").write_bytes(b"\xff\xd8")
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps([
        {"file": "logo.png", "answer": "Logo"},
        {"file": "person.jpg", "answer": "Person", "photo": True},
    ]))
    catalog = game.load_catalog(tmp_path, manifest)
    client = TestClient(create_app(tmp_path, manifest, secret_key="test"))
    client.post("/new", data={"mode": "classic"})
    for _ in range(2):
        page = client.get("/game").text
        item = catalog[image_id(page)]
        assert ("card logo photo" in page) == item.photo
        client.post("/guess", data={"image_id": item.id, "guess": item.answer})
