import json
import random

import pytest

from app import game


@pytest.fixture
def catalog(tmp_path):
    for name in ("a.png", "b.jpg", "c.svg"):
        (tmp_path / name).write_bytes(b"x")
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps([
        {"file": "a.png", "answer": "Java", "aliases": ["Java cup"]},
        {"file": "b.jpg", "answer": "Coca-Cola", "aliases": ["Coke"]},
        {"file": "c.svg", "answer": "Apple"},
    ]))
    return game.load_catalog(tmp_path, manifest)


def test_normalize_trims_collapses_and_ignores_case():
    assert game.normalize("  JaVa   Cup ") == "java cup"


def test_correct_ignores_case_and_whitespace(catalog):
    item = catalog[game.make_id("a.png")]
    assert game.is_correct(item, " java ")
    assert game.is_correct(item, "JAVA CUP")


def test_wrong_and_mistyped_guesses_fail(catalog):
    item = catalog[game.make_id("a.png")]
    assert not game.is_correct(item, "Jvaa")
    assert not game.is_correct(item, "")


def test_ids_do_not_leak_answers(catalog):
    for item_id in catalog:
        assert "java" not in item_id.lower()


def test_pick_next_shows_every_image_once_then_ends(catalog):
    rng = random.Random(1)
    seen: list[str] = []
    picked = []
    for _ in range(len(catalog)):
        choice, seen = game.pick_next(catalog, seen, rng)
        picked.append(choice)
    assert sorted(picked) == sorted(catalog)
    assert game.pick_next(catalog, seen, rng) == (None, seen)


def test_missing_manifest_gives_empty_catalog(tmp_path):
    assert game.load_catalog(tmp_path, tmp_path / "nope.json") == {}


def test_missing_image_file_is_an_error(tmp_path):
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps([{"file": "ghost.png", "answer": "Ghost"}]))
    with pytest.raises(game.CatalogError):
        game.load_catalog(tmp_path, manifest)


def test_entry_without_answer_is_an_error(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    manifest = tmp_path / "images.json"
    manifest.write_text(json.dumps([{"file": "a.png"}]))
    with pytest.raises(game.CatalogError):
        game.load_catalog(tmp_path, manifest)
