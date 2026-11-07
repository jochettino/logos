# 0001. Use uv for Python environments and dependencies

- Status: Accepted
- Date: 2026-11-07

## Context
- The project needs an isolated environment, a dependency manifest and a reproducible install, locally, in CI and on Vercel.
- The development machine (Debian/Ubuntu on WSL2) has Python 3.14 but no `pip` and no `python3-venv`. Creating a venv with the standard tools requires `sudo apt install python3.14-venv`.
- Vercel's default Python is 3.12 (3.13 and 3.14 are also supported), and the project is pinned to 3.12 in `.python-version`.
- Vercel reads dependencies from `pyproject.toml` (with or without `uv.lock`), `requirements.txt` or `Pipfile`, and the entrypoint from `[tool.vercel]` in `pyproject.toml`.
- The maintainer had not used `uv` before.

## Decision
We will use [uv](https://docs.astral.sh/uv/) to manage the virtual environment, Python version and dependencies.

- Dependencies and dev dependencies (`[dependency-groups] dev`) live in `pyproject.toml`; `uv.lock` is committed.
- Setup is `uv sync`; commands run through `uv run` (`uv run pytest`, `uv run uvicorn ...`).
- CI uses `astral-sh/setup-uv` with `uv sync --locked`, which fails if the lockfile is stale.
- `requirements.txt` and `requirements-dev.txt` were removed so there is a single dependency source.

Why: `uv` creates venvs and fetches the pinned Python itself, so it works on this machine without `sudo` or system packages. It installs from a lockfile for reproducible builds, and Vercel supports `pyproject.toml` with `uv.lock` directly.

## Alternatives Considered
- **`venv` + `pip` with `requirements.txt`**: the most conventional option and Vercel supports it. Ruled out because it needs `sudo apt install python3.14-venv` here, has no lockfile unless extra tooling is added, and does not manage Python versions.
- **Other tools (Poetry, Pipenv, pip-tools, etc.)**: not evaluated.

## Consequences
- Positive: one-command setup, fast installs, reproducible builds via `uv.lock`, no system-wide changes, one dependency source for local, CI and Vercel.
- Negative: contributors must install `uv`, which is one more tool to learn. The documented installer is a script downloaded from astral.sh.
- Negative: `uv.lock` must be kept in sync with `pyproject.toml`; CI enforces this with `--locked`.
- Open: not confirmed whether Vercel installs the `dev` dependency group, which would slightly enlarge the bundle.
