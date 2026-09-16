# AGENTS.md

Instructions for coding agents working in this repository — Claude Code, Cursor, Copilot, Aider,
or any other assistant. Human contributors follow the same conventions; see also
[CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

Django + HTMX + Alpine.js application to track changes in platform DDPs (data deletion policies).
Server-rendered Django templates with HTMX for interactivity and Alpine.js for light client-side
state — not a SPA. The only frontend build step is Sass → CSS (via Node, see below); there is no
JS bundler and none should be introduced without an explicit decision to do so.

## Toolchain — always use `uv`

This project uses [uv](https://docs.astral.sh/uv/) exclusively. Never call `pip`, `python -m venv`,
or a bare `python`/`pytest`/`django-admin` directly.

```bash
uv sync                          # install/update the environment from uv.lock
uv run manage.py <command>       # any Django management command
uv run pytest                    # test suite + coverage
uv add <package>                 # add a runtime dependency
uv add --group dev <package>     # add a dev-only dependency (linting, testing, etc.)
```

Adding a dependency with anything other than `uv add`/`uv add --group dev` (e.g. hand-editing
`pyproject.toml`) will leave `uv.lock` out of sync — always let uv update the lock file.

## Project layout

```
config/
  settings/
    base.py        # shared settings
    local.py        # local dev (DEBUG=True, sqlite fallback)
    production.py    # deploy (all secrets required, no defaults)
    cicd.py          # GitHub Actions (in-memory sqlite)
  urls.py, wsgi.py, asgi.py
apps/
  core/              # skeleton app — health check + index view; new apps go in apps/<name>/
    following this same shape (models.py, views.py, urls.py, tests.py, templates/<app>/)
assets/scss/         # Sass source (not Django-served) — see "Frontend assets" below
templates/           # project-level templates (base.html)
static/              # project-level static assets; static/css/ is compiled output, gitignored
```

Django apps live under `apps/<name>/`, not the repo root. Each app owns its own
`templates/<app_name>/` directory (Django's `APP_DIRS` convention) so template names never collide
across apps.

## Frontend assets (Sass)

Sass compiles with plain Node tooling (`npm run build` / `npm run watch`), not a Python/Django
package — deliberately kept out of `pyproject.toml` and `uv`'s dependency tree.

- Source: `assets/scss/` (7-1-lite: `abstracts/`, `base/`, `components/`, `layout/`, `main.scss`).
- Output: `static/css/main.css` — a build artifact, gitignored, never hand-edited or committed.
- `templates/base.html` links it with the plain `{% static 'css/main.css' %}` tag.
- Partials use the `@use` module system (`@use "../abstracts/variables" as *;`), not the legacy
  `@import` — Dart Sass (the compiler `npm run build` invokes) deprecates `@import`.
- CI runs `npm ci && npm run build` on every push/PR to catch breakage; there's no local
  pre-commit hook for it (add one if Sass changes become frequent enough to warrant it).

## Testing

Write tests with `django.test.TestCase` (unittest-style) — this is the project convention, not
plain pytest functions. Both of these run the exact same test files and must both keep working:

```bash
uv run manage.py test
uv run pytest
```

- Test files: `tests.py` for a small app, or a `tests/` package with `test_*.py` modules for a
  larger one — either is discovered by both runners.
- Coverage must stay at or above 80% (`--cov-fail-under=80` in `pyproject.toml`). Don't lower this
  threshold to make a change pass; write the missing tests instead.
- Migrations, `manage.py`, settings modules, and `wsgi.py`/`asgi.py` are excluded from coverage —
  don't add tests just to cover them.

## Before considering a change done

1. `uv run ruff check .` and `uv run ruff format .` — zero errors.
2. `uv run mypy .` — zero errors. Don't add `# type: ignore` to silence a real type error; fix it
   or narrow the type instead.
3. `uv run djlint . --check` for any template changes (`uv run djlint . --reformat` to fix).
4. `uv run pytest` — all green, coverage still ≥80%.
5. If `pyproject.toml`/`uv.lock` changed: `uv run pip-audit` clean (this also runs in pre-commit
   and CI automatically).

All of the above run in `.github/workflows/ci.yml` on every push/PR — a red CI run means one of
these steps would have failed locally too.

## Conventions

- Ruff's rule set is intentionally strict (see `pyproject.toml`) — annotate function signatures,
  avoid bare `except Exception`, use `pathlib` over `os.path`, etc. Per-file ignores already exist
  for migrations, tests, settings, and `manage.py` — don't add new blanket ignores without a reason
  in a comment next to them.
- Don't hand-edit files under `**/migrations/` — generate them with
  `uv run manage.py makemigrations` and commit the result.
- Settings differences between environments belong in `config/settings/`, never as
  `if DEBUG:`-style branching inside application code.
- Secrets/config come from environment variables via `django-environ` (see `.env.example`) — never
  hardcode a secret, and never commit a real `.env` file.
- Keep `CONTRIBUTING.md` in sync if you change the dev workflow (new required env var, new
  pre-commit hook, new CI job, etc.).
