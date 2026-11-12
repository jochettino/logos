# Adding images

The catalog lives in `app/catalog/`:

```
app/catalog/
  001-tech.yaml      one file per category (the number sets the menu order)
  002-adult.yaml
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
| `title` | file | yes | Button label. Free text, e.g. `+18` in `002-adult.yaml`. |
| `description` | file | no | Subtitle under the button. Defaults to empty. |
| `logos` | file | yes | List of logos; may be empty. |
| `file` | logo | yes | Image in `app/catalog/images/` (png, jpg, jpeg, gif, webp, svg, avif). |
| `answer` | logo | yes | The name players type. Matching ignores case and extra spaces. |
| `aliases` | logo | no | List of alternative names. |
| `photo` | logo | no | `true` for photos. Logos sit on a white card with padding; a photo fills the card edge to edge, cropped to fit, instead of showing white around it. |

## Adding a logo to an existing category

1. Copy the file into `app/catalog/images/`.
2. Add an entry to the `logos` list of the category file.

## Adding a category (game mode)

Create `app/catalog/<order>-<id>.yaml`, where `<order>` is a three digit number and `<id>` is the category name. The number decides the order of the buttons on the game selection screen and must be unique. Nothing else needs to change: the app scans the folder at startup.

## Quotes and types

The loader rejects values of the wrong type instead of guessing, so a few YAML traps are worth knowing:

- `answer: NO` is the boolean `false` and is rejected. Write `answer: "NO"`.
- `answer: 2024` is a number and is rejected. Write `answer: "2024"`.
- `photo` must be `true` or `false`, not `"yes"`.
- `aliases` must be a list, even with a single entry.

The app fails at startup with a clear error, naming the file and the entry, if a file name, `id`, order, image or field is malformed. Make sure you have the right to use any logo you add.
