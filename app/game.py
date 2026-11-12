"""Game logic: catalog loading, answer matching and image selection.

Everything here is pure (no FastAPI), so it is easy to unit test.
"""

import hashlib
import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}

# Category files are named <order>-<id>.yaml, e.g. 001-tech.yaml.
CATEGORY_FILE = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.ya?ml$")


class CatalogError(Exception):
    """Raised when a category file is malformed or references a missing file."""


@dataclass(frozen=True)
class Item:
    id: str  # opaque id exposed to the browser; never reveals the answer
    path: Path
    answer: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    photo: bool = False  # fill the whole card edge to edge instead of sitting on white

    def accepted_answers(self) -> set[str]:
        return {normalize(name) for name in (self.answer, *self.aliases)}


@dataclass(frozen=True)
class Category:
    """One game mode: a category file and the logos it lists."""

    id: str
    order: int  # from the file name prefix; the UI shows categories in this order
    title: str
    description: str
    items: dict[str, Item]  # keyed by opaque id


def normalize(text: str) -> str:
    """Fold a name for comparison: ignore case, accents and every space.

    "Leonardo Di Caprio", "leonardo dicaprio" and "Leonardo DiCaprio" all match, and
    "Jesús Gil" matches "Jesus Gil". Spelling is otherwise exact.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return "".join(plain.casefold().split())


def make_id(filename: str) -> str:
    return hashlib.sha256(filename.encode()).hexdigest()[:10]


def _read_category_file(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path.name} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"{path.name} must contain a YAML mapping")
    return data


def _text(where: str, field_name: str, value) -> str:
    """YAML would happily turn 2024 or NO into a number or a boolean; insist on text."""
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}: '{field_name}' must be a non-empty string")
    return value


def _load_items(path: Path, logos, images_dir: Path, seen_ids: set[str]) -> dict[str, Item]:
    if not isinstance(logos, list):
        raise CatalogError(f"{path.name} must have a 'logos' list")
    items: dict[str, Item] = {}
    for position, entry in enumerate(logos):
        where = f"{path.name} logo #{position}"
        if not isinstance(entry, dict):
            raise CatalogError(f"{where} must be a mapping with 'file' and 'answer'")
        filename = _text(where, "file", entry.get("file"))
        answer = _text(where, "answer", entry.get("answer"))
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            raise CatalogError(f"{where}: 'aliases' must be a list")
        aliases = tuple(_text(where, "aliases entry", alias) for alias in aliases)
        photo = entry.get("photo", False)
        if not isinstance(photo, bool):
            raise CatalogError(f"{where}: 'photo' must be true or false")

        image = images_dir / filename
        if image.suffix.lower() not in IMAGE_EXTENSIONS:
            raise CatalogError(f"Unsupported image type: {filename}")
        if not image.is_file():
            raise CatalogError(f"Image not found: {image}")
        item = Item(
            id=make_id(filename),
            path=image,
            answer=answer,
            aliases=aliases,
            photo=photo,
        )
        if item.id in seen_ids:
            raise CatalogError(f"Duplicate image entry: {filename}")
        seen_ids.add(item.id)
        items[item.id] = item
    return items


def load_catalog(catalog_dir: Path) -> list[Category]:
    """Read one JSON file per category, ordered by the number prefix in the file name."""
    images_dir = catalog_dir / "images"
    categories: list[Category] = []
    seen_ids: set[str] = set()
    seen_orders: dict[int, str] = {}

    for path in sorted([*catalog_dir.glob("*.yaml"), *catalog_dir.glob("*.yml")]):
        match = CATEGORY_FILE.match(path.name)
        if not match:
            raise CatalogError(f"{path.name} must be named like 001-tech.yaml")
        order, name = int(match.group(1)), match.group(2)

        data = _read_category_file(path)
        if data.get("id") != name:
            raise CatalogError(f"{path.name}: 'id' must be '{name}' to match the file name")
        title = _text(path.name, "title", data.get("title"))
        description = data.get("description", "")
        if not isinstance(description, str):
            raise CatalogError(f"{path.name}: 'description' must be a string")
        if order in seen_orders:
            raise CatalogError(f"{path.name}: order {order:03d} is already used by {seen_orders[order]}")

        seen_orders[order] = path.name
        categories.append(
            Category(
                id=name,
                order=order,
                title=title,
                description=description,
                items=_load_items(path, data.get("logos"), images_dir, seen_ids),
            )
        )

    return sorted(categories, key=lambda category: category.order)


def is_correct(item: Item, guess: str) -> bool:
    return normalize(guess) in item.accepted_answers()


def pick_next(
    catalog: dict[str, Item],
    seen: list[str],
    rng: random.Random | None = None,
) -> tuple[str | None, list[str]]:
    """Pick a random unseen image id. Returns (id, updated_seen).

    Returns (None, seen) once every image has been shown: the game is won.
    """
    rng = rng or random
    seen = [i for i in seen if i in catalog]
    unseen = [i for i in catalog if i not in seen]
    if not unseen:
        return None, seen
    choice = rng.choice(unseen)
    return choice, [*seen, choice]
