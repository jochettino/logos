"""Game logic: catalog loading, answer matching and image selection.

Everything here is pure (no FastAPI), so it is easy to unit test.
"""

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}

# Category files are named <order>-<id>.json, e.g. 001-tech.json.
CATEGORY_FILE = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")


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
    """Trim, collapse inner whitespace and ignore case."""
    return " ".join(text.split()).casefold()


def make_id(filename: str) -> str:
    return hashlib.sha256(filename.encode()).hexdigest()[:10]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{path.name} is not valid JSON: {exc}") from exc


def _load_items(path: Path, logos, images_dir: Path, seen_ids: set[str]) -> dict[str, Item]:
    if not isinstance(logos, list):
        raise CatalogError(f"{path.name} must have a 'logos' list")
    items: dict[str, Item] = {}
    for position, entry in enumerate(logos):
        where = f"{path.name} logo #{position}"
        if not isinstance(entry, dict) or not entry.get("file") or not entry.get("answer"):
            raise CatalogError(f"{where} needs 'file' and 'answer'")
        image = images_dir / entry["file"]
        if image.suffix.lower() not in IMAGE_EXTENSIONS:
            raise CatalogError(f"Unsupported image type: {entry['file']}")
        if not image.is_file():
            raise CatalogError(f"Image not found: {image}")
        item = Item(
            id=make_id(entry["file"]),
            path=image,
            answer=entry["answer"],
            aliases=tuple(entry.get("aliases", ())),
            photo=entry.get("photo", False) is True,
        )
        if item.id in seen_ids:
            raise CatalogError(f"Duplicate image entry: {entry['file']}")
        seen_ids.add(item.id)
        items[item.id] = item
    return items


def load_catalog(catalog_dir: Path) -> list[Category]:
    """Read one JSON file per category, ordered by the number prefix in the file name."""
    images_dir = catalog_dir / "images"
    categories: list[Category] = []
    seen_ids: set[str] = set()
    seen_orders: dict[int, str] = {}

    for path in sorted(catalog_dir.glob("*.json")):
        match = CATEGORY_FILE.match(path.name)
        if not match:
            raise CatalogError(f"{path.name} must be named like 001-tech.json")
        order, name = int(match.group(1)), match.group(2)

        data = _read_json(path)
        if not isinstance(data, dict):
            raise CatalogError(f"{path.name} must contain a JSON object")
        if data.get("id") != name:
            raise CatalogError(f"{path.name}: 'id' must be '{name}' to match the file name")
        title, description = data.get("title"), data.get("description", "")
        if not isinstance(title, str) or not title.strip():
            raise CatalogError(f"{path.name} needs a non-empty 'title'")
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
