# Contributing

## Setup

Local development runs in Docker Compose (Django, PostgreSQL, Mailpit): follow the
[README's quickstart](README.md#quickstart-docker), or its
[section on running without Docker](README.md#running-without-docker).

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Nothing is
installed globally — `uv` provisions its own Python and a project-local `.venv`. For the tooling
that runs on your machine (hooks, linters, docs), also:

```bash
uv sync
uv run pre-commit install
```

Uploaded DDPs are parsed by a background task. Locally (and in tests) it runs immediately inside the
request; in production the database task backend is used, which needs a worker process next to the
web server:

```bash
uv run manage.py db_worker
```

Uploaded files wait in `DDP_INCOMING_DIR` (default `var/incoming/`, gitignored, never served) only
until they're parsed, and are deleted right after, whether parsing succeeded or not. The web process
and the worker must both be able to reach that directory.

A maintenance command works on already stored schema documents (no re-upload needed):

```bash
uv run manage.py refresh_observations   # re-apply the parser's current rules (e.g. which nodes are data points)
uv run manage.py renormalize [--platform SLUG] [--dry-run]   # apply path rules / wrapper check to stored uploads
```

In production, run this daily (e.g. from cron): it deletes the uploaders' own values whose retention
time (`DDP_VALUES_RETENTION_DAYS`, default 30) is over; see `ddp_tracker/ddps/values.py`.

```bash
uv run manage.py purge_upload_values
```

Run any project command through `uv run` (e.g. `uv run manage.py shell`, `uv run ruff check .`)
so it uses the project's `.venv` rather than whatever Python happens to be on your `PATH`.

## Frontend assets (Sass)

Sass source lives in `assets/scss/` (following a lightweight [7-1-style layout](https://sass-guidelin.es/#the-7-1-pattern):
`abstracts/` for variables/mixins, `base/` for resets and typography, `components/`, `layout/`, all pulled together
by `main.scss`). It's compiled with:

```bash
npm run build   # one-off compile to static/css/main.css
npm run watch   # recompile on change while developing
```

Partials use Sass's `@use` module system, not the older `@import` — each partial
pulls in exactly the abstracts it needs via `@use "../abstracts/..." as *;`.

[Bootstrap 5.3](https://getbootstrap.com/docs/5.3/) is compiled in from `node_modules`
(`vendors/_bootstrap.scss`, configured with our design tokens); its JS bundle is served from
`static/vendor/`. Use its components and utilities for new UI and customise it through its
variables.

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

Workspace packages under `packages/` (e.g. `packages/ddp-parser`) are Django-free and test with plain
`unittest.TestCase`. `pytest` collects them with everything else; Django's runner only discovers
them when passed their path:

```bash
uv run manage.py test . packages/ddp-parser/tests
```

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
again in GitHub Actions on every push and pull request, alongside a Node job that runs
`npm ci && npm run build` to catch broken Sass, and a second test job against PostgreSQL (the
production database; it catches what SQLite hides, such as `jsonb` sorting JSON keys); a PR can't
merge with any of them red.

## Settings

Settings are split under `config/settings/`:

- `base.py` — shared by every environment
- `local.py` — local development (`DEBUG=True`, insecure default `SECRET_KEY`, Mailpit); the
  database comes from `.envs/.local/` (Docker) or `DATABASE_URL`
- `production.py` — deployment (everything sensitive required from the environment, no defaults —
  a missing `DJANGO_SECRET_KEY` or `DATABASE_URL` fails at startup rather than running insecurely)
- `cicd.py` — GitHub Actions (in-memory sqlite, no external services; `DATABASE_URL` overrides
  the database, as the PostgreSQL job does)

Upload-related settings: `DDP_INCOMING_DIR`, `DDP_MAX_UPLOAD_SIZE`, `DDP_SIMILARITY_THRESHOLD`
(below it, an upload is unusual and needs the uploader's confirmation and a staff approval before
it counts) and `TASKS_BACKEND` (see `.env.example`).

`manage.py` defaults to `local`; `config/wsgi.py`/`config/asgi.py` default to `production`. Override
with the `DJANGO_SETTINGS_MODULE` environment variable when you need something else.

## Dependencies

```bash
uv add <package>          # runtime dependency
uv add --group dev <package>   # dev-only dependency
uv sync                   # after pulling a branch with new deps
```

Commit the updated `uv.lock` alongside `pyproject.toml`. `pip-audit` runs
automatically on commit when either file changes.

## Git workflow

> **Status:** we're actively developing the first prototype. There is no release strategy yet (no
> versioning, release branches or tags); `stage` is only a test deployment. This section will grow
> once releases start.

### Branches

| Branch                         | Purpose                                                          | Who changes it          |
|--------------------------------|------------------------------------------------------------------|-------------------------|
| `dev`                          | integration branch: every change lands here first, through a PR  | maintainers (via PRs)   |
| `stage`                        | test release: `dev` merged in when it's ready to try out         | maintainers             |
| `main`                         | not used for development yet (see the status note above)         | —                       |
| `feat/…`, `fix/…`, `docs/…`, … | your work, one change per branch                                 | you                     |

### Step by step: contributing a change

1. **Start from an up-to-date `dev`:**

   ```bash
   git switch dev
   git pull origin dev
   ```

2. **Create a branch** with a short, descriptive name and a type prefix:

   ```bash
   git switch -c feat/ddp-diff-view        # or fix/htmx-partial-refresh, docs/setup-guide, …
   ```

3. **Commit your work** in small, focused commits. Write messages in the imperative mood
   (`add DDP diff endpoint`, not `added` / `adds`); a prefix like `feat:`, `fix:`, `chore:`,
   `refactor:` or `docs:` is encouraged but not enforced. The pre-commit hooks run on every commit;
   don't bypass them with `--no-verify`, fix what they report instead.

   ```bash
   git add -p                               # stage what belongs to this change
   git commit -m "feat: add DDP diff endpoint"
   ```

4. **Run the checks locally** (see [Code quality](#code-quality) and [Testing](#testing)), so CI
   doesn't find the problems for you:

   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run mypy .
   uv run djlint . --check
   just pytest                              # or: DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest
   ```

5. **Bring in the latest `dev`** if it moved on while you worked, and resolve any conflicts:

   ```bash
   git fetch origin
   git rebase origin/dev                    # or: git merge origin/dev
   ```

6. **Push the branch:**

   ```bash
   git push -u origin feat/ddp-diff-view
   ```

7. **Open a pull request against `dev`** (not `main`, the repository's default branch): on GitHub,
   choose `dev` as the base branch, or with the [GitHub CLI](https://cli.github.com/):

   ```bash
   gh pr create --base dev --title "feat: add DDP diff view" --body "What changes and why."
   ```

   Describe what the change does and why, and how to try it. CI (lint, tests on SQLite and
   PostgreSQL, pip-audit, the Sass build) runs on the PR and must be green. If CI fails, fix the
   cause; don't work around it.

8. **Review:** a maintainer reviews the PR. Address their comments with further commits on the
   same branch (`git push` updates the PR). Once it's approved and green, a maintainer merges it
   into `dev`. After the merge you can delete your branch:

   ```bash
   git switch dev
   git pull origin dev
   git branch -d feat/ddp-diff-view
   ```

### For maintainers: test release to `stage`

When `dev` is ready to be tried out, a maintainer merges it into `stage`:

```bash
git fetch origin
git switch stage
git pull origin stage
git merge --no-ff origin/dev             # a merge commit marks each test release
git push origin stage
```

`stage` only ever receives merges from `dev`: never commit to it directly, and fix problems found
on `stage` through the normal flow above (a branch from `dev`, a PR against `dev`).
