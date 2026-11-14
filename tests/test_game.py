import random

import pytest
import yaml

from app import game


@pytest.fixture
def catalog_dir(tmp_path):
    for name in ("a.png", "b.jpg", "c.svg"):
        (tmp_path / "images").mkdir(exist_ok=True)
        (tmp_path / "images" / name).write_bytes(b"x")
    (tmp_path / "images").mkdir(exist_ok=True)
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech",
        "title": "Tech",
        "description": "Tech logos",
        "logos": [
            {"file": "a.png", "answer": "Java", "aliases": ["Java cup"]},
            {"file": "b.jpg", "answer": "Coca-Cola", "aliases": ["Coke"]},
        ],
    }))
    (tmp_path / "002-adult.yaml").write_text(yaml.safe_dump({
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


def image_id(filename: str, data: bytes = b"x") -> str:
    """Id the catalog gives an image written by the fixtures above (they all hold b"x")."""
    return game.make_id(filename, data)


def test_categories_are_ordered_by_file_prefix(catalog_dir):
    (catalog_dir / "000-first.yaml").write_text(yaml.safe_dump({"id": "first", "title": "First", "logos": []}))
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


def test_normalize_ignores_case_and_spaces():
    assert game.normalize("  JaVa   Cup ") == "javacup"


def test_normalize_ignores_punctuation():
    assert game.normalize("Mercedes-Benz") == game.normalize("Mercedes Benz")
    assert game.normalize("AT&T") == "att"
    assert game.normalize("Coca-Cola") == game.normalize("coca cola")


def test_normalize_ignores_accents():
    assert game.normalize("Jesús Gil") == game.normalize("Jesus Gil")
    assert game.normalize("  ÁÉÍÓÚ  ") == "aeiou"


def test_punctuation_in_an_answer_does_not_matter(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.png", "answer": "Mercedes-Benz"}],
    }))
    item = next(iter(game.load_catalog(tmp_path)[0].items.values()))
    assert game.is_correct(item, "Mercedes Benz")
    assert game.is_correct(item, "mercedesbenz")
    assert not game.is_correct(item, "Mercedes")


def test_spacing_inside_a_name_does_not_matter(items):
    item = items[image_id("a.png")]
    assert game.is_correct(item, "JavaCup")
    assert game.is_correct(item, "j a v a  c u p")


def test_correct_ignores_case_and_whitespace(items):
    assert game.is_correct(items[image_id("a.png")], " java ")
    assert game.is_correct(items[image_id("a.png")], "JAVA CUP")


def test_wrong_and_mistyped_guesses_fail(items):
    assert not game.is_correct(items[image_id("a.png")], "Jvaa")
    assert not game.is_correct(items[image_id("a.png")], "")


def test_ids_do_not_leak_answers(items):
    for item_id in items:
        assert "java" not in item_id.lower()


def test_id_changes_when_the_image_bytes_change(catalog_dir):
    # This is what makes long-lived caching of /image/{id} safe: new bytes, new URL.
    before = next(iter(game.load_catalog(catalog_dir)[0].items))
    (catalog_dir / "images" / "a.png").write_bytes(b"new logo")
    assert next(iter(game.load_catalog(catalog_dir)[0].items)) != before


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
    (catalog_dir / "tech.yaml").write_text(yaml.safe_dump({"id": "tech", "title": "Tech", "logos": []}))
    with pytest.raises(game.CatalogError, match="001-tech.yaml"):
        game.load_catalog(catalog_dir)


def test_id_must_match_the_file_name(catalog_dir):
    (catalog_dir / "003-misc.yaml").write_text(yaml.safe_dump({"id": "other", "title": "Misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="'id' must be 'misc'"):
        game.load_catalog(catalog_dir)


def test_missing_title_is_an_error(catalog_dir):
    (catalog_dir / "003-misc.yaml").write_text(yaml.safe_dump({"id": "misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="title"):
        game.load_catalog(catalog_dir)


def test_duplicate_order_prefix_is_an_error(catalog_dir):
    (catalog_dir / "002-misc.yaml").write_text(yaml.safe_dump({"id": "misc", "title": "Misc", "logos": []}))
    with pytest.raises(game.CatalogError, match="order 002"):
        game.load_catalog(catalog_dir)


def test_invalid_yaml_is_an_error(catalog_dir):
    (catalog_dir / "003-misc.yaml").write_text("id: [unclosed")
    with pytest.raises(game.CatalogError, match="not valid YAML"):
        game.load_catalog(catalog_dir)


def test_logos_must_be_a_list(catalog_dir):
    (catalog_dir / "003-misc.yaml").write_text(yaml.safe_dump({"id": "misc", "title": "Misc", "logos": {}}))
    with pytest.raises(game.CatalogError, match="'logos' list"):
        game.load_catalog(catalog_dir)


def test_missing_image_file_is_an_error(tmp_path):
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [{"file": "ghost.png", "answer": "Ghost"}],
    }))
    with pytest.raises(game.CatalogError, match="Image not found"):
        game.load_catalog(tmp_path)


def test_entry_without_answer_is_an_error(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.png"}],
    }))
    with pytest.raises(game.CatalogError, match="'answer' must be a non-empty string"):
        game.load_catalog(tmp_path)


def test_unsupported_image_type_is_an_error(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.txt").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.txt", "answer": "A"}],
    }))
    with pytest.raises(game.CatalogError, match="Unsupported image type"):
        game.load_catalog(tmp_path)


def test_the_same_image_cannot_be_listed_twice(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    logo = {"file": "a.png", "answer": "A"}
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({"id": "tech", "title": "Tech", "logos": [logo]}))
    (tmp_path / "002-misc.yaml").write_text(yaml.safe_dump({"id": "misc", "title": "Misc", "logos": [logo]}))
    with pytest.raises(game.CatalogError, match="Duplicate image entry"):
        game.load_catalog(tmp_path)


def test_photo_defaults_to_false_and_is_read_from_the_file(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "images" / "b.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [
            {"file": "a.png", "answer": "A"},
            {"file": "b.png", "answer": "B", "photo": True},
        ],
    }))
    items = game.load_catalog(tmp_path)[0].items
    assert items[image_id("a.png")].photo is False
    assert items[image_id("b.png")].photo is True


def test_yml_extension_is_supported(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yml").write_text(yaml.safe_dump({
        "id": "tech", "title": "Tech", "logos": [{"file": "a.png", "answer": "A"}],
    }))
    assert [category.id for category in game.load_catalog(tmp_path)] == ["tech"]


@pytest.mark.parametrize("answer", ["NO", "2024", "null"])
def test_yaml_non_string_answers_are_rejected(tmp_path, answer):
    # Unquoted NO, 2024 and null are not strings in YAML; accepting them would break matching.
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(
        f"id: tech\ntitle: Tech\nlogos:\n  - file: a.png\n    answer: {answer}\n"
    )
    with pytest.raises(game.CatalogError, match="'answer' must be a non-empty string"):
        game.load_catalog(tmp_path)


def test_photo_must_be_a_boolean(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(
        "id: tech\ntitle: Tech\nlogos:\n  - file: a.png\n    answer: A\n    photo: 'yes'\n"
    )
    with pytest.raises(game.CatalogError, match="'photo' must be true or false"):
        game.load_catalog(tmp_path)


def test_aliases_must_be_a_list(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.png").write_bytes(b"x")
    (tmp_path / "001-tech.yaml").write_text(
        "id: tech\ntitle: Tech\nlogos:\n  - file: a.png\n    answer: A\n    aliases: K8s\n"
    )
    with pytest.raises(game.CatalogError, match="'aliases' must be a list"):
        game.load_catalog(tmp_path)


def test_category_file_must_be_a_mapping(tmp_path):
    (tmp_path / "001-tech.yaml").write_text("- just\n- a list\n")
    with pytest.raises(game.CatalogError, match="must contain a YAML mapping"):
        game.load_catalog(tmp_path)


def write_one_logo_category(directory, **fields):
    """Smallest valid category file, plus whatever extra fields the test needs."""
    (directory / "images").mkdir(exist_ok=True)
    (directory / "images" / "only.svg").write_bytes(b"x")
    (directory / "001-tech.yaml").write_text(yaml.safe_dump({
        "id": "tech",
        "title": "Tech",
        "logos": [{"file": "only.svg", "answer": "Only"}],
        **fields,
    }))
    return directory


def test_sample_framed_and_prompt_default_to_off(categories):
    tech = categories[0]
    assert (tech.sample, tech.framed, tech.prompt) == (None, False, "Brand or product name")


def test_sample_framed_and_prompt_are_read_from_file(tmp_path):
    write_one_logo_category(tmp_path, sample=1, framed=True, prompt="Country name")
    (tech,) = game.load_catalog(tmp_path)
    assert (tech.sample, tech.framed, tech.prompt) == (1, True, "Country name")


@pytest.mark.parametrize("sample", [0, -1, 1.5, "30", True])
def test_sample_must_be_a_positive_whole_number(tmp_path, sample):
    write_one_logo_category(tmp_path, sample=sample)
    with pytest.raises(game.CatalogError, match="'sample' must be a whole number of at least 1"):
        game.load_catalog(tmp_path)


def test_sample_cannot_be_larger_than_the_category(tmp_path):
    write_one_logo_category(tmp_path, sample=2)
    with pytest.raises(game.CatalogError, match="'sample' is 2 but only 1 logos are listed"):
        game.load_catalog(tmp_path)


def test_framed_must_be_a_boolean(tmp_path):
    write_one_logo_category(tmp_path, framed="yes")
    with pytest.raises(game.CatalogError, match="'framed' must be true or false"):
        game.load_catalog(tmp_path)


def test_prompt_must_be_a_non_empty_string(tmp_path):
    write_one_logo_category(tmp_path, prompt="")
    with pytest.raises(game.CatalogError, match="'prompt' must be a non-empty string"):
        game.load_catalog(tmp_path)


def test_draw_pool_without_a_sample_returns_every_image(categories):
    tech = categories[0].items
    pool = game.draw_pool(tech, None)
    assert pool == tech and pool is not tech


def test_draw_pool_returns_a_random_subset(categories):
    tech = categories[0].items
    pool = game.draw_pool(tech, 1, random.Random(1))
    assert len(pool) == 1 and set(pool) <= set(tech)


def test_draw_pool_varies_between_games(categories):
    tech = categories[0].items
    pools = {frozenset(game.draw_pool(tech, 1, random.Random(seed))) for seed in range(20)}
    assert len(pools) > 1


def test_draw_pool_can_sample_the_whole_category(categories):
    tech = categories[0].items
    assert set(game.draw_pool(tech, len(tech), random.Random(1))) == set(tech)
