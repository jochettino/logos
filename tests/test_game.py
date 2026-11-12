import json
import random

import pytest

from app import game


@pytest.fixture
def catalog_dir(tmp_path):
    for name in ("a.png", "b.jpg", "c.svg"):
        (tmp_path / "images").mkdir(exist_ok=True)
        (tmp_path / "images" / name).write_bytes(b"x")
    (tmp_path / "images").mkdir(exist_ok=True)
    (tmp_path / "001-tech.json").write_text(json.dumps({
        "id": "tech",
        "title": "Tech",
        "description": "Tech logos",
        "logos": [
            {"file": "a.png", "answer": "Java", "aliases": ["Java cup"]},
            {"file": "b.jpg", "answer": "Coca-Cola", "aliases": ["Coke"]},
        ],
    }))
    (tmp_path / "002-adult.json").write_text(json.dumps({
        "id": "adult",
        "title": "+18",
        "description": "Adult logos",
        "logos": [{"file": "c.svg", "answer": "Apple"}],
    }))
    return tmp_path


@pytest.fixture
def categories(catalog_dir):
    return game.load_catalog(catalog_dir)


@pytest.fixture
def items(categories):
    return {item_id: item for category in categories for item_id, item in category.items.items()}


def test_categories_are_ordered_by_file_prefix(catalog_dir):
    (catalog_dir / "000-first.json").write_text(json.dumps({"id": "first", "title": "First", "logos": []}))
    assert [c.id for c in game.load_catalog(catalog_dir)] == ["first", "tech", "adult"]


def test_category_fields_are_read_from_file(categories):
    tech, adult = categories
    assert (tech.id, tech.order, tech.title, tech.description) == ("tech", 1, "Tech", "Tech logos")
    assert (adult.id, adult.order, adult.title, adult.description) == ("adult", 2, "+18", "Adult logos")


def test_title_does_not_have_to_match_the_id(categories):
    assert categories[1].id == "adult" and categories[1].title == "+18"


def test_each_category_holds_only_its_own_logos(categories):
    tech, adult = categories
    assert len(tech.items) == 2 and len(adult.items) == 1


def test_normalize_trims_collapses_and_ignores_case():
    assert game.normalize("  JaVa   Cup ") == "java cup"


def test_correct_ignores_case_and_whitespace(items):
    assert game.is_correct(items[game.make_id("a.png")], " java ")
    assert game.is_correct(items[game.make_id("a.png")], "JAVA CUP")


def test_wrong_and_mistyped_guesses_fail(items):
    assert not game.is_correct(items[game.make_id("a.png")], "Jvaa")
    assert not game.is_correct(items[game.make_id("a.png")], "")


def test_ids_do_not_leak_answers(items):
    for item_id in items:
        assert "java" not in item_id.lower()


def test_pick_next_shows_every_image_once_then_ends(categories):
    tech = categories[0].items
    rng = random.Random(1)
    seen: list[str] = []
    picked = []
    for _ in range(len(tech)):
        choice, seen = game.pick_next(tech, seen, rng)
        picked.append(choice)
    assert sorted(picked) == sorted(tech)
    assert game.pick_next(tech, seen, rng) == (None, seen)


def test_empty_catalog_dir_gives_no_categories(tmp_path):
    assert game.load_catalog(tmp_path) == []


def test_bad_file_name_is_an_error(catalog_dir):
    (catalog_dir / "tech.json").write_text(json.dumps({"id": "tech", "title": "Tech", "logos": []}))
    with pytest.raises(game.CatalogError, match="001-tech.json"):
        game.load_catalog(catalog_dir)


def test_id_must_match_the_file_name(catalog_dir):
    (catalog_dir / "003-misc.json").write_text(json.dumps({"id": "other", "title": "Misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="'id' must be 'misc'"):
        game.load_catalog(catalog_dir)


def test_missing_title_is_an_error(catalog_dir):
    (catalog_dir / "003-misc.json").write_text(json.dumps({"id": "misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="title"):
        game.load_catalog(catalog_dir)


def test_duplicate_order_prefix_is_an_error(catalog_dir):
    (catalog_dir / "002-misc.json").write_text(json.dumps({"id": "misc", "title": "Misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="order 002"):
        game.load_catalog(catalog_dir)


def test_invalid_json_is_an_error(catalog_dir):
    (catalog_dir / "003-misc.json").write_text("{not json")
    with pytest.raises(game.CatalogError, match="not valid JSON"):
        game.load_catalog(catalog_dir)


def test_logos_must_be_a_list(catalog_dir):
    (catalog_dir / "003-misc.json").write_text(json.dumps({"id": "misc", "title": "Misc", "logos": {}}))
    with pytest.raises(game.CatalogError, match="'logos' list"):
        game.load_catalog(catalog_dir)


def test_missing_image_file_is_an_error(tmp_path):
    (tmp_path / "001-tech.json").write_text(json.dumps({
        "id": "tech", "title": "Tech", "logos": [{"file": "ghost.png", "answer": "Ghost"}],
    }))
    with pytest.raises(game.CatalogError, match="Image not found"):
        game.load_catalog(tmp_path)


def test_entry_without_answer_is_an_error(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.json").write_text(json.dumps({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.png"}],
    }))
    with pytest.raises(game.CatalogError, match="needs 'file' and 'answer'"):
        game.load_catalog(tmp_path)


def test_unsupported_image_type_is_an_error(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.txt").write_bytes(b"x")
    (tmp_path / "001-tech.json").write_text(json.dumps({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.txt", "answer": "A"}],
    }))
    with pytest.raises(game.CatalogError, match="Unsupported image type"):
        game.load_catalog(tmp_path)


def test_the_same_image_cannot_be_listed_twice(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    logo = {"file": "a.png", "answer": "A"}
    (tmp_path / "001-tech.json").write_text(json.dumps({"id": "tech", "title": "Tech", "logos": [logo]}))
    (tmp_path / "002-misc.json").write_text(json.dumps({"id": "misc", "title": "Misc", "logos": [logo]}))
    with pytest.raises(game.CatalogError, match="Duplicate image entry"):
        game.load_catalog(tmp_path)


def test_photo_defaults_to_false_and_is_read_from_the_file(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "images" / "b.png").write_bytes(b"x")
    (tmp_path / "001-tech.json").write_text(json.dumps({
        "id": "tech", "title": "Tech", "logos": [
            {"file": "a.png", "answer": "A"},
            {"file": "b.png", "answer": "B", "photo": True},
        ],
    }))
    items = game.load_catalog(tmp_path)[0].items
    assert items[game.make_id("a.png")].photo is False
    assert items[game.make_id("b.png")].photo is True
