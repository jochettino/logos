# Adding images

1. Copy the file into `app/images/` (png, jpg, jpeg, gif, webp, svg, avif).
2. Add an entry to `app/images.json`:

   ```json
   {"file": "java.png", "answer": "Java", "aliases": ["Java cup"]}
   ```

   `aliases` is optional. Matching ignores case and extra whitespace, and is otherwise exact.

The app fails at startup with a clear error if an entry is malformed or points to a missing file. The bundled `sample-*.svg` files are placeholders: delete them once you add real logos. Make sure you have the right to use any logo you add.
