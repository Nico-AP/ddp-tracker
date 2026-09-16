# ddp-tracker

A web application to track changes in platform DDPs.

Django + [HTMX](https://htmx.org/) + [Alpine.js](https://alpinejs.dev/) — server-rendered
templates, with a small Node/Sass build for CSS only.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and [Node](https://nodejs.org/).

```bash
uv sync
uv run pre-commit install
uv run manage.py migrate
npm install
npm run build
uv run manage.py runserver
```

Visit `http://localhost:8000/`.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full dev workflow (testing, linting, settings
layout, dependency management, git conventions). Coding agents should also read
[AGENTS.md](AGENTS.md).
