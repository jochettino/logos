# Adding images

The catalog lives in `app/catalog/`:

```
app/catalog/
  001-tech.yaml      one file per category (the number sets the menu order)
  002-motor.yml
  003-flags.yaml     Country Flags, built from https://github.com/lipis/flag-icons
  999-adult.yaml     the 999 prefix keeps the adult category last
  images/            the image files themselves
```

Category files are YAML. Indentation is significant, and values that could be read as numbers or booleans must be quoted (`answer: "NO"`). See [ADR 0003](adr/0003-use-yaml-for-the-catalog.md) for why YAML.

## Category file template

```yaml
# Required. Must match the name part of the file name: 001-tech.yaml -> id: tech.
id: tech

# Required. The label on the game selection button; free text, so it may differ from id.
title: Tech

# Optional. The line shown under the button. Defaults to empty. Quote it if it could
# be read as another type.
description: Tools, brands and products from the tech world

# Optional. Images shown per game, drawn at random. Without it a game goes through
# every image. The flags category uses it because it holds far more flags than one
# game should last.
sample: 30

# Optional. Draw a thin border around the image. Flags with white edges (Japan,
# Cyprus) would otherwise blend into the white card. Defaults to false.
framed: true

# Optional. Placeholder in the guess field. Defaults to "Brand or product name".
prompt: Country name

# Required. The logos of this category, shown in a random order during the game.
# Every logo needs 'file' and 'answer'; 'aliases' and 'photo' are optional.
logos:
  - file: java.png            # required, a file in app/catalog/images/
    answer: Java              # required, the name players have to type
    aliases:                  # optional, other names that also count as correct
      - Java cup
    photo: false              # optional, true for photos (see below); defaults to false

  - file: docker.png
    answer: Docker
```

Field summary:

| Field | Where | Required | Notes |
| --- | --- | --- | --- |
| `id` | file | yes | Must match the file name after the number: `001-tech.yaml` needs `tech`. |
| `title` | file | yes | Button label. Free text, e.g. `+18` in `999-adult.yaml`. |
| `description` | file | no | Subtitle under the button. Defaults to empty. |
| `sample` | file | no | Images per game, drawn at random. Defaults to the whole category. Must be at least 1 and no larger than the list. |
| `framed` | file | no | `true` to outline the image, for art that blends into the white card. Defaults to false. |
| `prompt` | file | no | Placeholder in the guess field. Defaults to `Brand or product name`. |
| `logos` | file | yes | List of logos; may be empty. |
| `file` | logo | yes | Image in `app/catalog/images/` (png, jpg, jpeg, gif, webp, svg, avif). |
| `answer` | logo | yes | The name players type. Matching ignores case and extra spaces. |
| `aliases` | logo | no | Other names that also count. Only needed for genuinely different names, not spellings that differ by case, accents, spaces or punctuation. |
| `photo` | logo | no | `true` for photos. Logos sit on a white card with padding; a photo fills the card edge to edge, cropped to fit, instead of showing white around it. |

## Adding a logo to an existing category

1. Copy the file into `app/catalog/images/`.
2. Add an entry to the `logos` list of the category file.

## Adding a category (game mode)

Create `app/catalog/<order>-<id>.yaml`, where `<order>` is a three digit number and `<id>` is the category name. The number decides the order of the buttons on the game selection screen and must be unique. Nothing else needs to change: the app scans the folder at startup.

Leave the first numbers free for categories that should come first, and give a category a high one (`999-adult.yaml`) when it must stay at the end of the menu for good.

A category with many images should set `sample`, so a game is a few random ones instead of all of them: `003-flags.yaml` plays 30 of its flags per game. The sample is drawn when the game starts and kept in the session cookie, so it stays the same for that game without any server state.

`003-flags.yaml` only lists well-known countries: a wrong guess must feel like a fair miss, not a flag nobody has ever seen. That is a curation choice, not a technical one, so add or remove entries freely; the source set lives at https://github.com/lipis/flag-icons.

## Quotes and types

The loader rejects values of the wrong type instead of guessing, so a few YAML traps are worth knowing:

- `answer: NO` is the boolean `false` and is rejected. Write `answer: "NO"`.
- `answer: 2024` is a number and is rejected. Write `answer: "2024"`.
- `photo` must be `true` or `false`, not `"yes"`.
- `aliases` must be a list, even with a single entry.

The app fails at startup with a clear error, naming the file and the entry, if a file name, `id`, order, image or field is malformed. Make sure you have the right to use any logo you add.
