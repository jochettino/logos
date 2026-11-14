import json

import yaml
import re

import pytest
from fastapi.testclient import TestClient

from app import game
from app.main import create_app


IMAGE_BYTES = b"\x89PNG"


def write_category(directory, name, title, logos, description="", **fields):
    """Write <name>.yaml plus the images it lists into a catalog directory."""
    (directory / "images").mkdir(parents=True, exist_ok=True)
    for logo in logos:
        (directory / "images" / logo["file"]).write_bytes(IMAGE_BYTES)
    category_id = name.split("-", 1)[1]
    (directory / f"{name}.yaml").write_text(yaml.safe_dump({
        "id": category_id,
        "title": title,
        "description": description,
        "logos": logos,
        **fields,
    }))
    return directory


@pytest.fixture
def catalog_dir(tmp_path):
    return write_category(
        tmp_path,
        "001-tech",
        "Tech",
        [{"file": "only.png", "answer": "Java", "aliases": ["Java cup"]}],
        description="Tech logos only",
    )


@pytest.fixture
def client(catalog_dir):
    client = TestClient(create_app(catalog_dir, secret_key="test"))
    client.post("/new", data={"mode": "tech"})
    return client


@pytest.fixture
def multi(tmp_path):
    logos = [{"file": "Alpha.png", "answer": "Alpha"}, {"file": "Beta.png", "answer": "Beta"}]
    write_category(tmp_path, "001-tech", "Tech", logos)
    client = TestClient(create_app(tmp_path, secret_key="test"))
    client.post("/new", data={"mode": "tech"})
    client.catalog = {item_id: item for category in game.load_catalog(tmp_path) for item_id, item in category.items.items()}
    return client


def answer_of(client):
    """Answer of the image currently shown (test-only peek into the catalog)."""
    return client.catalog[image_id(client.get("/game").text)].answer


def image_id(html: str) -> str:
    return html.split("/image/")[1].split('"')[0]


def catalog_id(filename: str) -> str:
    """Id the server assigns to an image written by write_category."""
    return game.make_id(filename, IMAGE_BYTES)


def status(html: str) -> tuple[int, int]:
    """(score, best) as shown in the header pills."""
    return (
        int(re.search(r"Score <b>(\d+)</b>", html).group(1)),
        int(re.search(r"Best <b>(\d+)</b>", html).group(1)),
    )


def play(client, text):
    page = client.get("/game").text
    return client.post("/guess", data={"image_id": image_id(page), "guess": text}).text


def play_swapping(client, text):
    """Guess the way the page does with JS: ask for the swapped fragment, not a redirect."""
    page = client.get("/game").text
    response = client.post(
        "/guess",
        data={"image_id": image_id(page), "guess": text},
        headers={"X-Logos-Swap": "1"},
    )
    return response, response.text


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


def test_pages_have_link_preview_metadata(client):
    page = client.get("/").text
    assert '<meta property="og:title" content="Logos — name that brand">' in page
    assert "One wrong answer ends the game." in page
    assert 'property="og:image" content="http://testserver/static/og-image.png"' in page
    assert '<meta name="twitter:card" content="summary_large_image">' in page


def test_page_links_a_standalone_manifest(client):
    page = client.get("/").text
    assert 'rel="manifest" href="http://testserver/static/manifest.webmanifest"' in page
    assert '<meta name="mobile-web-app-capable" content="yes">' in page


def test_page_loads_vercel_analytics(client):
    page = client.get("/").text
    assert '<script defer src="/_vercel/insights/script.js"></script>' in page
    assert "window.va = window.va ||" in page


def test_manifest_is_served_as_manifest_json(client):
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert purposes == {"any", "maskable"}


@pytest.mark.parametrize("icon", ["icon-192.png", "icon-512.png", "icon-maskable-512.png"])
def test_manifest_icons_are_served(client, icon):
    response = client.get(f"/static/{icon}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_preview_image_is_served(client):
    response = client.get("/static/og-image.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_about_credits_thesvg_and_the_brands(client):
    page = client.get("/about").text
    assert "non-profit" in page
    assert "belongs to its respective company" in page
    assert "public internet" in page
    assert 'href="https://github.com/glincker/thesvg"' in page


def test_share_button_appears_after_a_loss_with_score_and_category(multi):
    page = play(multi, "nope")
    assert "Share my score" in page
    assert 'data-share-text="I scored 0 in Tech at Logos' in page
    assert 'data-share-url="http://testserver/"' in page


def test_share_button_appears_on_a_win(multi):
    page = ""
    for _ in range(2):
        page = play(multi, answer_of(multi))
    assert "You won!" in page and "Share my score" in page
    assert 'data-share-text="I scored 2 in Tech at Logos' in page


def test_no_share_button_while_playing(client):
    assert "Share my score" not in client.get("/game").text


def test_game_links_back_to_main_menu(client):
    page = client.get("/game").text
    assert "Main menu" in page and "New game" not in page


def test_playing_from_menu_starts_fresh_game_keeping_best(multi):
    play(multi, answer_of(multi))
    page = multi.post("/new", data={"mode": "tech"}).text
    assert status(page) == (0, 1)


def test_guess_field_is_inside_a_submit_form(client):
    page = client.get("/game").text
    form = page.split('class="guess"')[1].split("</form>")[0]
    assert 'name="guess"' in form and 'type="submit"' in form


def test_guess_field_is_not_autofocused_in_html(client):
    # Autofocus would pop up the on-screen keyboard on phones; game.js focuses on desktop only.
    assert "autofocus" not in client.get("/game").text


def test_game_page_loads_the_focus_script(client):
    assert "/static/game.js" in client.get("/game").text
    assert client.get("/static/game.js").status_code == 200


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


def test_wrong_guess_ends_game_and_reveals_the_answer(multi):
    answer = answer_of(multi)
    page = play(multi, "nope")
    assert "Oh, no!" in page and "Your streak ends here" in page and "Game over" in page and "Play again" in page and "Main menu" in page and "/image/" not in page
    assert f"The answer was <b>{answer}</b>." in page


def test_revealed_answer_lists_the_aliases(client):
    assert "The answer was <b>Java</b> (Java cup)." in play(client, "nope")


def test_winning_does_not_reveal_any_answer(multi):
    page = ""
    for _ in range(2):
        page = play(multi, answer_of(multi))
    assert "The answer was" not in page


def test_guess_after_game_over_is_ignored(multi):
    page = multi.get("/game").text
    item = image_id(page)
    play(multi, "nope")
    page = multi.post("/guess", data={"image_id": item, "guess": "Alpha"}).text
    assert "Game over" in page and status(page)[0] == 0


def test_game_page_exposes_the_swap_targets(client):
    page = client.get("/game").text
    assert 'id="pills"' in page and 'id="play"' in page


def test_guess_can_answer_with_a_fragment_instead_of_a_redirect(multi):
    response, fragment = play_swapping(multi, "nope")
    assert response.status_code == 200 and "location" not in response.headers
    assert 'id="pills"' in fragment and '<div id="play"' in fragment
    # A fragment, not a page: no head, no brand header, nothing to re-parse or re-render.
    assert "<html" not in fragment and "game-header" not in fragment


def test_fragment_carries_the_new_score_and_the_next_image(multi):
    _, fragment = play_swapping(multi, answer_of(multi).lower())
    assert "Score <b>001</b>" in fragment and "Best <b>001</b>" in fragment
    assert "/image/" in fragment and 'data-body-class=""' in fragment


def test_fragment_for_a_wrong_guess_shows_the_game_over_screen(multi):
    answer = answer_of(multi)
    _, fragment = play_swapping(multi, "nope")
    assert "Game over" in fragment and 'data-body-class="lost"' in fragment
    assert "/image/" not in fragment and f"The answer was <b>{answer}</b>" in fragment


def test_blank_guess_fragment_keeps_the_same_image(multi):
    page = multi.get("/game").text
    response = multi.post(
        "/guess",
        data={"image_id": image_id(page), "guess": "  "},
        headers={"X-Logos-Swap": "1"},
    )
    assert "Type a guess first" in response.text
    assert image_id(response.text) == image_id(page)


def test_a_repeated_swap_guess_does_not_score_twice(multi):
    page = multi.get("/game").text
    data = {"image_id": image_id(page), "guess": multi.catalog[image_id(page)].answer}
    multi.post("/guess", data=data, headers={"X-Logos-Swap": "1"})
    repeated = multi.post("/guess", data=data, headers={"X-Logos-Swap": "1"})
    assert "Score <b>001</b>" in repeated.text


def test_guess_without_the_swap_header_still_redirects(client):
    page = client.get("/game").text
    response = client.post(
        "/guess", data={"image_id": image_id(page), "guess": "Java"}, follow_redirects=False
    )
    assert response.status_code == 303 and response.headers["location"] == "/game"


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
    assert "You won!" in page and "Main menu" in page and status(page) == (2, 2) and "/image/" not in page


def test_best_score_survives_a_new_game(multi):
    play(multi, answer_of(multi))
    play(multi, "nope")
    page = multi.post("/new", data={"mode": "tech"}).text
    assert status(page) == (0, 1) and "/image/" in page


def test_best_score_only_grows(multi):
    play(multi, answer_of(multi))
    play(multi, "nope")
    multi.post("/new", data={"mode": "tech"})
    play(multi, "nope")
    assert status(multi.get("/game").text)[1] == 1


def test_new_game_mid_game_restarts_keeping_best(multi):
    play(multi, answer_of(multi))
    page = multi.post("/new", data={"mode": "tech"}).text
    assert status(page) == (0, 1) and "Game over" not in page


def test_legacy_cookie_starts_fresh_and_keeps_score_as_best(client):
    from itsdangerous import TimestampSigner
    import base64

    data = base64.b64encode(json.dumps({"score": 5, "attempts": 9, "seen": [], "current": "x"}).encode())
    client.cookies.clear()
    client.cookies.set("session", TimestampSigner("test").sign(data).decode())
    client.post("/new", data={"mode": "tech"})
    assert status(client.get("/game").text) == (0, 5)


def test_image_is_served_and_unknown_id_404s(client):
    item_id = image_id(client.get("/game").text)
    assert client.get(f"/image/{item_id}").content == b"\x89PNG"
    assert client.get("/image/nope").status_code == 404


def test_image_url_is_cached_indefinitely(client):
    # Safe because the id hashes the image bytes: new content means a new URL.
    item_id = image_id(client.get("/game").text)
    assert client.get(f"/image/{item_id}").headers["cache-control"] == "public, max-age=31536000, immutable"


def test_static_assets_are_cached_briefly(client):
    # Asset file names have no content hash, so they must expire sooner than images.
    assert client.get("/static/style.css").headers["cache-control"] == "public, max-age=300"


def test_category_without_logos_shows_friendly_message(tmp_path):
    write_category(tmp_path, "001-tech", "Tech", [])
    client = TestClient(create_app(tmp_path, secret_key="test"))
    client.post("/new", data={"mode": "tech"})
    assert "No images configured" in client.get("/game").text


def test_bundled_catalog_is_valid():
    from app.main import CATALOG_DIR

    categories = game.load_catalog(CATALOG_DIR)
    assert [category.id for category in categories] == ["tech", "motor", "flags", "adult"]
    assert all(category.items for category in categories)


def test_bundled_flags_category_plays_a_sample():
    from app.main import CATALOG_DIR

    flags = {category.id: category for category in game.load_catalog(CATALOG_DIR)}["flags"]
    assert flags.sample == 30 and len(flags.items) > flags.sample
    assert flags.framed and flags.prompt == "Country name"


def test_bundled_flags_are_the_best_known_countries():
    from app.main import CATALOG_DIR

    flags = {category.id: category for category in game.load_catalog(CATALOG_DIR)}["flags"]
    answers = {item.answer for item in flags.items.values()}
    assert {"Germany", "United States of America", "Japan", "Brazil", "Kenya"} <= answers
    # Obscure flags made the game unplayable: they stay out of the curated pool.
    assert not {"Nauru", "Tuvalu", "Saint Kitts and Nevis", "Comoros"} & answers


def test_bundled_catalog_has_no_redundant_aliases():
    from app.main import CATALOG_DIR

    for category in game.load_catalog(CATALOG_DIR):
        for item in category.items.values():
            forms = [game.normalize(name) for name in (item.answer, *item.aliases)]
            assert len(forms) == len(set(forms)), f"{item.answer} has an alias that normalises the same"


@pytest.fixture
def mixed(tmp_path):
    """Two categories with different logos each."""
    write_category(
        tmp_path, "001-tech", "Tech",
        [{"file": "Alpha.png", "answer": "Alpha"}, {"file": "Gamma.png", "answer": "Gamma"}],
    )
    write_category(tmp_path, "002-adult", "+18", [{"file": "Beta.png", "answer": "Beta"}])
    return TestClient(create_app(tmp_path, secret_key="test"))


def logos_in(client, mode):
    client.post("/new", data={"mode": mode})
    return int(re.search(r"Logo \d+ of (\d+)", client.get("/game").text).group(1))


def test_mode_screen_uses_category_title_and_description(client):
    page = client.get("/play").text
    assert "Tech" in page and 'value="tech"' in page and "Tech logos only" in page


def test_mode_screen_lists_categories_in_file_order(mixed):
    page = mixed.get("/play").text
    assert page.index('value="tech"') < page.index('value="adult"')
    assert "+18" in page


def test_game_without_a_mode_redirects_to_mode_screen(mixed):
    response = mixed.get("/game", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/play"


def test_unknown_mode_is_rejected(mixed):
    response = mixed.post("/new", data={"mode": "nope"}, follow_redirects=False)
    assert response.headers["location"] == "/play"


def test_each_category_plays_only_its_logos(mixed):
    assert logos_in(mixed, "tech") == 2
    assert logos_in(mixed, "adult") == 1


def test_modes_only_serve_their_own_logos(mixed):
    adult, tech = catalog_id("Beta.png"), catalog_id("Alpha.png")
    mixed.post("/new", data={"mode": "tech"})
    assert mixed.get(f"/image/{adult}").status_code == 404
    assert mixed.get(f"/image/{tech}").status_code == 200
    mixed.post("/new", data={"mode": "adult"})
    assert mixed.get(f"/image/{adult}").status_code == 200
    assert mixed.get(f"/image/{tech}").status_code == 404


def test_play_again_keeps_the_mode(mixed):
    assert logos_in(mixed, "adult") == 1
    mixed.post("/guess", data={"image_id": image_id(mixed.get("/game").text), "guess": "nope"})
    page = mixed.get("/game").text
    assert 'name="mode" value="adult"' in page
    mixed.post("/new", data={"mode": "adult"})
    assert "+18" in mixed.get("/game").text


def test_best_score_is_kept_per_mode(mixed):
    mixed.post("/new", data={"mode": "tech"})
    for _ in range(2):
        page = mixed.get("/game").text
        answer = next(n for n in ("Alpha", "Beta", "Gamma") if catalog_id(f"{n}.png") == image_id(page))
        mixed.post("/guess", data={"image_id": image_id(page), "guess": answer})
    assert status(mixed.get("/game").text) == (2, 2)
    mixed.post("/new", data={"mode": "adult"})
    assert status(mixed.get("/game").text) == (0, 0)
    mixed.post("/new", data={"mode": "tech"})
    assert status(mixed.get("/game").text) == (0, 2)


def test_photo_entries_fill_the_card_and_logos_do_not(tmp_path):
    write_category(
        tmp_path, "001-tech", "Tech",
        [{"file": "logo.png", "answer": "Logo"}, {"file": "person.jpg", "answer": "Person", "photo": True}],
    )
    catalog = {
        item_id: item
        for category in game.load_catalog(tmp_path)
        for item_id, item in category.items.items()
    }
    client = TestClient(create_app(tmp_path, secret_key="test"))
    client.post("/new", data={"mode": "tech"})
    for _ in range(2):
        page = client.get("/game").text
        item = catalog[image_id(page)]
        assert ("card logo photo" in page) == item.photo
        client.post("/guess", data={"image_id": item.id, "guess": item.answer})


@pytest.fixture
def sampled(tmp_path):
    """A category that shows two of its five images per game."""
    logos = [{"file": f"Name{number}.png", "answer": f"Name{number}"} for number in range(5)]
    write_category(tmp_path, "001-flags", "Flags", logos, sample=2)
    client = TestClient(create_app(tmp_path, secret_key="test"))
    client.post("/new", data={"mode": "flags"})
    client.catalog = {
        item_id: item for category in game.load_catalog(tmp_path)
        for item_id, item in category.items.items()
    }
    return client


def test_sampled_game_only_plays_the_sample(sampled):
    page = sampled.get("/game").text
    assert "Logo 1 of 2" in page
    assert page.count('<span class="seg') == 2


def test_sampled_game_is_won_after_the_sample(sampled):
    for _ in range(2):
        play(sampled, answer_of(sampled))
    page = sampled.get("/game").text
    assert "You won!" in page and status(page) == (2, 2)


def test_sampled_game_starts_with_a_new_sample_after_a_loss(sampled):
    play(sampled, "nope")
    page = sampled.post("/new", data={"mode": "flags"}).text
    assert "Logo 1 of 2" in page and "/image/" in page and "Game over" not in page


def test_category_can_set_a_frame_and_a_prompt(tmp_path):
    write_category(
        tmp_path, "001-flags", "Flags",
        [{"file": "spain.svg", "answer": "Spain"}],
        framed=True, prompt="Country name",
    )
    client = TestClient(create_app(tmp_path, secret_key="test"))
    client.post("/new", data={"mode": "flags"})
    page = client.get("/game").text
    assert 'class="card logo framed"' in page
    assert 'placeholder="Country name"' in page


def test_default_category_has_no_frame_and_the_brand_prompt(client):
    page = client.get("/game").text
    assert 'class="card logo"' in page
    assert 'placeholder="Brand or product name"' in page
