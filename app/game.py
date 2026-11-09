"""Game logic: catalog loading, answer matching and image selection.

Everything here is pure (no FastAPI), so it is easy to unit test.
"""

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}


class CatalogError(Exception):
    """Raised when images.json is malformed or references a missing file."""


@dataclass(frozen=True)
class Item:
    id: str  # opaque id exposed to the browser; never reveals the answer
    path: Path
    answer: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    category: str | None = None  # not used by the game yet

    def accepted_answers(self) -> set[str]:
        return {normalize(name) for name in (self.answer, *self.aliases)}


def normalize(text: str) -> str:
    """Trim, collapse inner whitespace and ignore case."""
    return " ".join(text.split()).casefold()


def make_id(filename: str) -> str:
    return hashlib.sha256(filename.encode()).hexdigest()[:10]


def load_catalog(images_dir: Path, manifest: Path) -> dict[str, Item]:
    """Read the manifest and return items keyed by their opaque id."""
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{manifest} is not valid JSON: {exc}") from exc

    if not isinstance(entries, list):
        raise CatalogError(f"{manifest} must contain a JSON list")

    catalog: dict[str, Item] = {}
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("file") or not entry.get("answer"):
            raise CatalogError(f"{manifest} entry #{position} needs 'file' and 'answer'")
        path = images_dir / entry["file"]
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise CatalogError(f"Unsupported image type: {entry['file']}")
        if not path.is_file():
            raise CatalogError(f"Image not found: {path}")
        category = entry.get("category")
        if category is not None and not isinstance(category, str):
            raise CatalogError(f"{manifest} entry #{position}: 'category' must be a string")
        item = Item(
            id=make_id(entry["file"]),
            path=path,
            answer=entry["answer"],
            aliases=tuple(entry.get("aliases", ())),
            category=category,
        )
        if item.id in catalog:
            raise CatalogError(f"Duplicate image entry: {entry['file']}")
        catalog[item.id] = item
    return catalog


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
