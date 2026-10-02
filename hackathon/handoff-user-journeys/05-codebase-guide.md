# 05. Codebase guide

Everything here was checked against the `dev` branch at commit `a18b3f3` (30 September 2026). Upstream moves fast, so fetch `upstream/dev` first and re-check anything that looks different.

**Read the repository's own `AGENTS.md` and `CONTRIBUTING.md` before writing code.** This file summarises them and adds what we learned.

## Stack

- **Backend:** Django 5.2, PostgreSQL in production (SQLite works locally), django-allauth (email login with mandatory verification), django-tasks (background parsing).
- **Pages:** server-rendered templates with htmx (`static/vendor/htmx.min.js`) and Bootstrap 5.3 (compiled from Sass). Alpine.js is mentioned in the docs, but base.html does not load it; check before relying on it.
- **Parser:** `packages/ddp-parser`, a separate, Django-free package (a uv workspace member, import name `ddp_parser`).
- **Tooling:** Python 3.14 (`.python-version`; `requires-python >= 3.12`), managed with **uv only**; Node for Sass.

## Repository map

```
config/settings/     base.py, local.py (DEBUG, debug toolbar), production.py (CSP), cicd.py
config/urls.py       includes each app; "" is shared by schemas, reviews and core (core:index is "/")
ddp_tracker/
  core/              home page (core/index.html), health, docs view, template tags (core_tags.py)
  ddps/              Platform, Upload, UploadValues, PathRule; upload form, parse task, checks, approvals
  schemas/           Location, Observation; explorer, filters, profiles, timeline, triage, examples
  reviews/           review of an upload (no models)
  proposals/         suggestions workflow (non-staff changes, staff decide)
  annotations/       Annotation
  representations/   Representation, RepresentationMetadata, vocabularies (ActorType, ActivityType, ObjectType, MetadataRole)
  users/             custom User (email login), auth helpers (users/auth.py: signed_in_user)
  templates/         base.html (header and navigation), error pages
  static/            css/ and vendor/ are BUILD OUTPUT (npm run build); js/ holds our scripts
assets/scss/         Sass sources: abstracts, base, components, layout, pages (empty), themes, vendors, main.scss
packages/ddp-parser/ the parser
docs/docs/           MkDocs user guide and technical reference (concepts.md holds the definitions)
```

**App shape:**

- `apps.py`, with a class named like `ReviewsConfig` and `name = "ddp_tracker.<app>"`;
- `models.py`, `views.py`, `urls.py` (with `app_name`);
- `templates/<app>/` (Django's `APP_DIRS` convention; template names never collide);
- `tests.py` or `tests/test_*.py`.

**Registering a new app:**

1. Add it to `LOCAL_APPS` in `config/settings/base.py`.
2. Include its URLs in `config/urls.py`.

To take over `/`, include the new app's URLs **before** `ddp_tracker.core.urls`, or change `core:index`. Note that `base.html` links the brand to `core:index`.

## Conventions you must follow

- **uv only:** `uv sync`, `uv run manage.py …`, `uv run pytest`, `uv add` (never pip, never a bare python for project commands).
- **Content security policy** (production): `script-src 'self'` plus a nonce, `style-src 'self'`, `img-src 'self' data:`, `font-src 'self'`.
  - **No inline scripts, no inline styles (`style="…"`), no `eval`, no external fonts or CDNs.**
  - Put styles in Sass (a new partial in `assets/scss/pages/` or `components/`, imported from `main.scss` with `@use`).
  - Put scripts in `ddp_tracker/static/js/`, loaded with `defer`.
- **Bootstrap first:**
  - Use Bootstrap components and utilities, and customise through Sass variables or `--bs-*` custom properties.
  - Buttons always name a variant: `btn btn-primary`, `btn btn-outline-secondary btn-sm`, never a bare `btn`.
  - Tables use plain Bootstrap classes.
  - The shared dialog is a native `<dialog class="dialog">`, not `.modal`.
- **No JavaScript bundler.** Sass is compiled with `npm run build`, and `static/css/main.css` is never committed.
- **Tests:**
  - Use `django.test.TestCase` (unittest style).
  - Both `uv run pytest` and `uv run manage.py test` must pass.
  - pytest runs with `filterwarnings = error` (warnings fail tests) and `--cov-fail-under=80`.
- **Commits:** small and focused, imperative mood, prefix such as `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`. Pre-commit hooks (ruff, formatting and others) run on commit; do not bypass them with `--no-verify`.
- **Privacy:** never show uploaders' emails; accounts appear as `#id`. Do not add anything that stores raw DDP values.

## Permissions today

- **Three tiers:** anonymous, signed in, staff (`is_staff`). Django groups and permissions are not used.
- **Anonymous users** can explore everything public: platforms, explorer, annotations, representations, vocabulary, docs.
- **Signed-in users** can:
  - upload, and see only their own uploads;
  - suggest curation changes;
  - edit example values directly.
- **Staff:**
  - their changes apply directly;
  - they see all uploads;
  - they have the approvals and suggestion queues;
  - they have Django admin access.
- **Platforms, path rules and vocabulary approval** are managed in the Django admin only.

## Main models (short)

| Model | Key fields |
|---|---|
| `ddps.Platform` | name, slug |
| `ddps.Upload` | platform, requested_at, language, request_mode (DL_APP, DL_BROWSER, PAPI), request_format (json, csv), file_format (zip, json, csv), file_name (anonymised), uploaded_by, status, document (schema JSON), plausibility, registered_at, root_format |
| `schemas.Location` | platform, path, parent_path, name, annotation (FK), ignored, example_values (list of `{value, source}`) |
| `schemas.Observation` | upload × location: kind, is_data_point, type, shape, format, details, suggestions (the source of truth for everything descriptive) |
| `annotations.Annotation` | platform, name (unique per platform), description, note, pii; has many Locations |
| `representations.Representation` | location, pattern (activity, object, unmapped), name, description, note, actor, activity, object, target (vocabulary FKs) |
| `representations.RepresentationMetadata` | representation, location (below it), role, subject |
| `proposals.Proposal` | kind, status, values, base, targets |

**Descriptive facts** (type, shape, format, first and last seen) are computed at query time from Observations (`schemas/profiles.py`, `schemas/timeline.py`), restricted by a `SchemaFilter`.

## URL names

See the table in `03-site-structure.md`, "Existing real pages". Two gotchas:

- There is no global annotation list; it is per platform: `annotations:annotations` with a slug.
- `docs` takes a path argument: `reverse("docs", args=[""])` is the docs home, and `"guide/privacy/"` is the privacy page.

## Existing tests that the change will affect

`ddp_tracker/core/tests/tests.py`, class `IndexViewTests`:

- asserts that `core:index` renders `core/index.html`;
- counts `href` occurrences of the Explore URL on the home page (count=4: the header plus three cards);
- checks the header's Explore link.

If `/` becomes the role picker, or the navigation changes, **update these tests deliberately** (do not delete them): move them to the new home page or keep `core:index` working at another URL.

## How to run it (verified in the cloud container on 30 September 2026)

```bash
# Get the code (the fork is public; no credentials needed to clone)
git clone https://github.com/hekmatov/ddp-tracker && cd ddp-tracker
git remote add upstream https://github.com/Nico-AP/ddp-tracker && git fetch upstream
git switch -c feat/user-journeys upstream/dev

# Install
uv sync
npm ci && npm run build          # CSS and vendor JS; without this, pages are unstyled

# Local database without Docker
export DATABASE_URL=sqlite:///$PWD/demo.sqlite3 USE_DOCKER=no \
       DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
uv run manage.py migrate
uv run manage.py runserver 127.0.0.1:8000     # run in the background for screenshots

# Tests (in-memory SQLite; 492 tests passed in about 16 s on a18b3f3)
DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q
```

**Logging in locally:**

- Accounts need a verified email address. For a demo admin, create the user and an `allauth.account.models.EmailAddress(verified=True, primary=True)`, as the loading script in `07-demo-data.md` does.
- In tests, use `self.client.force_login(user)`.

**Screenshots:**

- Use `screenshot_example.py` in this folder, with the system `python3` (Playwright and Chromium are preinstalled).
- The local settings show django-debug-toolbar; the script hides it with injected CSS.
- `reference-screenshots/` shows the current home page and explorer, for comparison.

**Docker** (`just up` or `docker compose -f docker-compose.local.yml up`) is the upstream way to run it with PostgreSQL. It was not needed for our checks.

## Getting commits into Hekmat's repository

Hekmat's local clone is on his computer (`DDP-Tracker` folder). The shell on his computer is a sandbox:

- it has git and network access to GitHub;
- each call is limited to 180 seconds;
- uv and Python 3.10 are there, but the project wants Python 3.12 or later;
- whether uv can download packages there was not tested.

**Recommended workflow:**

1. Build and test in the **cloud container** clone, on `feat/user-journeys`.
2. When ready, make a bundle of the branch:
   `git bundle create user-journeys.bundle feat/user-journeys ^upstream/dev`
3. Save it to `DDP-Tracker-docs/bundles/`.
4. On Hekmat's computer (device shell, both folders mounted under `$HOME/mnt/`), run:

   ```bash
   cd "$HOME/mnt/DDP-Tracker"
   git fetch upstream
   git fetch ../DDP-Tracker-docs/bundles/user-journeys.bundle feat/user-journeys:feat/user-journeys
   git log --oneline -5 feat/user-journeys
   ```

5. Hekmat then pushes from Windows: `git push -u origin feat/user-journeys`.

**Environment gotchas we hit:**

- **Git lock files:** git in the connected folder needs **delete permission** (it creates and removes `.lock` files). Request it once for `DDP-Tracker`.
- **File modes:** the clone on Hekmat's computer has `core.filemode false`, so Windows Git does not flag every file as changed.
- **pycache:** Python writes `__pycache__` folders when tests run. They are gitignored; do not commit them.
