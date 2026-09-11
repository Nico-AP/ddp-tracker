# ddp-tracker

A web application to track changes in platform DDPs.

Django + [HTMX](https://htmx.org/) + [Alpine.js](https://alpinejs.dev/) — server-rendered
templates, no separate frontend build.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pre-commit install
uv run manage.py migrate
uv run manage.py runserver
```

Visit `http://localhost:8000/`.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full dev workflow (testing, linting, settings
layout, dependency management, git conventions). Coding agents should also read
[AGENTS.md](AGENTS.md).
