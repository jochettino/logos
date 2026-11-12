# Adding images

The catalog lives in `app/catalog/`:

```
app/catalog/
  001-tech.json      one file per category (the number sets the menu order)
  002-adult.json
  images/            the image files themselves
```

## Adding a logo to an existing category

1. Copy the file into `app/catalog/images/` (png, jpg, jpeg, gif, webp, svg, avif).
2. Add it to the `logos` list of the category file:

   ```json
   {"file": "java.png", "answer": "Java", "aliases": ["Java cup"]}
   ```

   `aliases` is optional. Matching ignores case and extra whitespace, and is otherwise exact.

   `photo` is optional, `true` or omitted. Logos sit on a white card with padding; a photo (for example a person) should set `"photo": true` so it fills the card edge to edge, cropped to fit, instead of showing white around it.

## Adding a category (game mode)

Create `app/catalog/<order>-<id>.json`, where `<order>` is a three digit number and `<id>` is the category name:

```json
{
  "id": "tech",
  "title": "Tech",
  "description": "Tools, brands and products from the tech world",
  "logos": [
    {"file": "java.png", "answer": "Java"},
    {"file": "docker.png", "answer": "Docker"}
  ]
}
```

- `id` must match the name part of the file name (`001-tech.json` needs `"id": "tech"`).
- `order` (the number prefix) decides the order of the buttons on the game selection screen and must be unique.
- `title` is the button label, so it does not have to match the `id` (`002-adult.json` uses `"title": "+18"`).
- `description` is the line shown under the button; it may be empty.

The app fails at startup with a clear error if a file name, `id`, order, image or entry is malformed. Make sure you have the right to use any logo you add.
