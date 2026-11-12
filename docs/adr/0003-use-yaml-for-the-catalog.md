# 0003. Use YAML for the catalog files

- Status: Accepted
- Date: 2026-11-12

## Context
The catalog is split into one file per category (`app/catalog/001-tech.yaml`, `002-adult.yaml`, ...). These files are content, not code: they are edited by hand whenever a logo, an alias or a whole game mode is added.

They were previously JSON. JSON is unambiguous and needs no extra dependency, but every edit costs punctuation: braces, commas between list items, and quotes around the aliases. A missing or extra comma is a common way to break the file, and the diff of adding one logo is noisy.

The files are small and shallow (a category, plus a list of logos with one or two optional fields each), so readability for a human editor matters more than machine friendliness.

## Decision
We will keep the catalog in YAML, one file per category, loaded with `yaml.safe_load`.

Because YAML coerces unquoted values (`NO` becomes `false`, `2024` becomes an integer, `null` becomes `None`), the loader validates every field's type and fails at startup with an error naming the file and entry, rather than guessing. Documentation calls out the traps and uses quotes where needed.

## Alternatives Considered
- **JSON**: kept the zero-dependency loader, but it is noisier to hand-edit and comma-fragile.
- **TOML**: good for flat configuration, awkward for a nested list of records, and less common for content files.
- **A database or CMS**: removes the file format question, but adds infrastructure and a deployment step for static content that changes rarely.
- **Python modules or a CSV**: either code as content or a format that cannot express the optional fields cleanly.

## Consequences
- The catalog is easier to read and edit by hand, and diffs are smaller when adding a logo.
- `PyYAML` becomes a runtime dependency and must be installed on every deploy target.
- The loader carries extra type checks and tests to compensate for YAML's implicit typing.
- Editors without YAML support may still break indentation; errors are caught at startup, not at request time.
