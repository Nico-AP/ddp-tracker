# ddp-tracker

A web application to track how platforms' data download packages (DDPs) change over time. People
upload the DDP they requested from a platform (TikTok, Instagram, …). Each upload is parsed into a
schema of its files and data points and registered into that platform's collected schema. Curators
then annotate the data points and say what lists' entries represent, in terms shared across platforms.

Privacy by design: an uploaded DDP is parsed and deleted right away. Only its schema is kept (never
the raw file), and the file name is stored anonymized.

**Stack:** Django, server-rendered templates with [htmx](https://htmx.org/) and
[Alpine.js](https://alpinejs.dev/), Bootstrap 5 compiled from Sass, and PostgreSQL. The parser is a
separate, Django-free package in [`packages/ddp-parser`](packages/ddp-parser) (a uv workspace
member).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose
- [Node](https://nodejs.org/), to compile the CSS on your machine; the containers don't include it
- [uv](https://docs.astral.sh/uv/), for pre-commit, docs and running things outside Docker
- Optional: [just](https://github.com/casey/just), for short commands. Every `just` recipe below
  also has its plain `docker compose` equivalent. To install it:

  ```bash
  brew install just               # macOS (Homebrew)
  uv tool install rust-just       # any platform, with uv (puts `just` on your PATH)
  ```

  Other package managers are listed in [just's installation guide](https://just.systems/man/en/packages.html).
  `just --list` shows all recipes.

## Quickstart (Docker)

```bash
npm install
npm run build                 # Sass -> ddp_tracker/static/css/, htmx + Bootstrap JS -> ddp_tracker/static/vendor/
just build                    # docker compose -f docker-compose.local.yml build
just up                       # docker compose -f docker-compose.local.yml up -d
```

This starts three containers:

| Service    | What                                                                    | URL                   |
|------------|-------------------------------------------------------------------------|-----------------------|
| `django`   | the app; runs `migrate`, then a dev server that reloads on code changes | http://localhost:8000 |
| `postgres` | PostgreSQL 18; data kept in a Docker volume                             | (Docker network only) |
| `mailpit`  | catches all outgoing mail                                               | http://localhost:8025 |

The repository is mounted into the `django` container, so code and template edits apply right away.
The dev defaults (database credentials etc.) are committed in `.envs/.local/`, so there's nothing to
copy or configure.

Then create an admin account:

```bash
just manage createsuperuser   # docker compose -f docker-compose.local.yml run --rm django python manage.py createsuperuser
```

Accounts sign in with their email address, and the address must be verified. Log in at
http://localhost:8000/accounts/login/, then open the verification mail in Mailpit
(http://localhost:8025).

Uploads are parsed right in the request locally, so no background worker is needed. Production
uses a database task queue with a worker; see [CONTRIBUTING.md](CONTRIBUTING.md#setup).

## Everyday commands

| `just`                  | `docker compose -f docker-compose.local.yml …`    | What                                         |
|-------------------------|---------------------------------------------------|----------------------------------------------|
| `just up` / `just down` | `up -d` / `down`                                  | start / stop the stack                       |
| `just logs [service]`   | `logs -f [service]`                               | follow the logs                              |
| `just manage <cmd>`     | `run --rm django python manage.py <cmd>`          | any management command                       |
| `just pytest [args]`    | `run --rm django pytest [args]`                   | the test suite, on PostgreSQL                |
| `just build`            | `build`                                           | rebuild the image (after dependency changes) |
| `just prune`            | `down -v`                                         | stop and **delete the database volume**      |

While working on styles, keep the Sass compiler running on your machine:

```bash
npm run watch
```

## Running without Docker

For quick checks, you can also run the app directly on your machine with uv. There's no Postgres or
Mailpit this way, so point it at SQLite (or a PostgreSQL of your own) and print mail to the console:

```bash
uv sync
export DATABASE_URL=sqlite:///db.sqlite3          # or postgres://user:password@localhost:5432/ddp_tracker
export USE_DOCKER=no
export DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```

SQLite hides some PostgreSQL-only behaviour. For example, PostgreSQL's `jsonb` reorders JSON keys.
So run the tests against PostgreSQL (`just pytest`, and CI does too) before relying on a change.

To keep these variables in a file instead, copy `.env.example` to `.env`, fill it in, and
`export DJANGO_READ_DOT_ENV_FILE=True`.

## Tests and checks

```bash
just pytest                                                    # in Docker, on PostgreSQL
DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest      # on your machine, in-memory SQLite
```

Linting, formatting, type checks and the pre-commit hooks (`uv run pre-commit install`) are covered
in [CONTRIBUTING.md](CONTRIBUTING.md). CI runs all of them, and the tests on both SQLite and
PostgreSQL.

## Documentation

The concepts and the parser spec live in [`docs/`](docs/docs) (MkDocs).

```bash
just docs                                 # live preview in Docker on http://localhost:9000
                                          # (docker compose -f docker-compose.docs.yml up --build)
uv run mkdocs serve -f docs/mkdocs.yml    # the same without Docker, on http://localhost:8001
uv run mkdocs build -f docs/mkdocs.yml    # builds docs/site/, which the app serves at /docs/
```

## Project layout

```
config/               settings (base, local, production, cicd), urls
ddp_tracker/          the Django apps: ddps (uploads), schemas, reviews, annotations,
                      representations, proposals, users, core
packages/ddp-parser/  the DDP parser (no Django)
assets/scss/          Sass sources; compiled into ddp_tracker/static/css/
docs/                 MkDocs documentation
compose/, .envs/      Docker images and environment for local development and production
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow (testing, linting, settings,
dependencies, git conventions). Coding agents should also read [AGENTS.md](AGENTS.md).
