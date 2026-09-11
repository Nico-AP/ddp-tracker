# Contributing

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Nothing is
installed globally — `uv` provisions its own Python and a project-local `.venv`.

```bash
uv sync
uv run pre-commit install
cp .env.example .env   # only needed if you want to override local defaults (e.g. Postgres)
uv run manage.py migrate
uv run manage.py runserver
```

Run any project command through `uv run` (e.g. `uv run manage.py shell`, `uv run ruff check .`)
so it uses the project's `.venv` rather than whatever Python happens to be on your `PATH`.

## Testing

Tests are written with Django's `django.test.TestCase`, same as `manage.py test`. Nothing about
that changes — `pytest-django` runs standard `TestCase` subclasses without modification, it just
adds coverage reporting, fixtures, and `--reuse-db` on top. Both of these work interchangeably:

```bash
uv run manage.py test        # Django's own runner
uv run pytest                # same tests, plus coverage report (--cov-fail-under=80)
```

Use whichever fits the moment — `manage.py test` for a quick check while developing, `pytest` when
you want the coverage report or to run a single test with `-k`. Test files must be named
`tests.py`, `test_*.py`, or `*_test.py` so both runners discover them the same way.

## Code quality

All checks run via `pre-commit` (installed above) on every commit:

- **ruff** — lint + format (replaces flake8/isort/black)
- **mypy** — static typing, via `django-stubs`
- **djlint** — lint + format for Django templates
- **pip-audit** — scans dependencies for known vulnerabilities, only when `pyproject.toml` or
  `uv.lock` changes

Run everything by hand at any time:

```bash
uv run pre-commit run --all-files
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run djlint . --check
uv run pytest
uv run manage.py test
```

The same checks (minus pip-audit's "only when deps changed" gating — it always runs in CI) run
again in GitHub Actions on every push and pull request; a PR can't merge with them red.

## Settings

Settings are split under `config/settings/`:

- `base.py` — shared by every environment
- `local.py` — local development (`DEBUG=True`, sqlite fallback, insecure default `SECRET_KEY`)
- `production.py` — deployment (everything sensitive required from the environment, no defaults —
  a missing `DJANGO_SECRET_KEY` or `DATABASE_URL` fails at startup rather than running insecurely)
- `cicd.py` — GitHub Actions (in-memory sqlite, no external services)

`manage.py` defaults to `local`; `config/wsgi.py`/`config/asgi.py` default to `production`. Override
with the `DJANGO_SETTINGS_MODULE` environment variable when you need something else.

## Dependencies

```bash
uv add <package>          # runtime dependency
uv add --group dev <package>   # dev-only dependency
uv sync                   # after pulling a branch with new deps
```

Commit the updated `uv.lock` alongside `pyproject.toml`. `pip-audit` runs automatically on commit
when either file changes.

## Git workflow

- Branch off `main` (or `dev`, if that's the current integration branch) with a short descriptive
  name, e.g. `feature/ddp-diff-view`, `fix/htmx-partial-refresh`.
- Keep commits scoped to one logical change. Write commit messages in the imperative mood
  (`add DDP diff endpoint`, not `added` / `adds`) — a short prefix like `feat:`, `fix:`, `chore:`,
  `refactor:`, or `docs:` is encouraged but not enforced.
- Open a PR against `main`; CI (lint + tests + pip-audit) must pass before merging.
- Don't bypass `pre-commit` (`--no-verify`) or CI failures — fix the underlying issue.
