# Adding images

1. Copy the file into `app/images/` (png, jpg, jpeg, gif, webp, svg, avif).
2. Add an entry to `app/images.json`:

   ```json
   {"file": "java.png", "answer": "Java", "aliases": ["Java cup"]}
   ```

   `aliases` is optional. Matching ignores case and extra whitespace, and is otherwise exact.

   `category` is optional, a string. Game modes pick logos by category: Classic uses `"tech"`, 18+ uses `"tech"` and `"adult"` (see `MODES` in `app/game.py`). A logo without a category counts as `"tech"`.

   `photo` is optional, `true` or omitted. Logos sit on a white card with padding; a photo (for example a person) should set `"photo": true` so it fills the card edge to edge, cropped to fit, instead of showing white around it.

The app fails at startup with a clear error if an entry is malformed or points to a missing file. Make sure you have the right to use any logo you add.
