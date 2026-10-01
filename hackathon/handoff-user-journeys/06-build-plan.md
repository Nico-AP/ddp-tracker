# 06. Build plan

## Phases

Work in this order, and **show Hekmat screenshots at the end of phases 2, 3 and 4** before moving on. Each check-in is short: send the screenshots, say what is done and what comes next, and ask whether anything should change.

| Phase | What | Output |
|---|---|---|
| 0. Set up | Clone the fork in the cloud container, add upstream, branch `feat/user-journeys` from the latest `upstream/dev`, `uv sync`, `npm ci && npm run build`, run the tests once (all green before you start) | A working environment |
| 1. Demo data | Management command `seed_demo` (spec in `07-demo-data.md`) with tests | A fresh DB becomes a demo in one command |
| 2. Landing and journeys | New app `journeys`, `content.py` with the eight roles and their steps, landing page at `/`, journey page template, navigation update, tests | Role picker and eight journeys; steps link to real pages and to placeholder prototype pages |
| 3. Mock-ups for researchers and engineers | M1 Concepts, M2 Concept detail, M3 Shortlist (with exports), M5 Changes, M6 API | The core "two views and a hand-off" story works end to end |
| 4. Remaining mock-ups | M4 Compare, M7 Snapshots, M8 Request instructions, M9 Moderator dashboard, M10 Seed from documentation, M11 Roles, M12 Learn | Every journey step leads somewhere meaningful |
| 5. Polish and deliver | Accessibility and phone-width pass, full test run, screenshots, bundle, `RUN-THE-PROTOTYPE.md`, summary | Delivered (see "Delivery") |

## File layout (proposed)

```
ddp_tracker/journeys/
  __init__.py
  apps.py                 JourneysConfig, name = "ddp_tracker.journeys"
  content.py              ROLES: list of roles; each has slug, name, card line, goal, audience, steps
                          STEP: title, text, url_name, url_args (optional), status ("available" or "prototype"),
                                needs ("anyone", "account", "staff"), missing (optional text), feature_ref
  prototype_data.py       fixed fictional data for mock-ups: themes, relevance scores, official documentation
                          snippets, snapshots, request instructions, role assignments, learner quiz
  views.py                index, journey, and one view per mock-up page
  urls.py                 app_name = "journeys"; "", "journeys/<slug:role>/", "prototype/…"
  templates/journeys/
    index.html            landing page
    journey.html          one template for all journeys
    _prototype_banner.html
    _step.html
    prototype/concepts.html, concept.html, shortlist.html, compare.html, changes.html, api.html,
              snapshots.html, request.html, moderate.html, seed.html, roles.html, learn.html
  management/commands/seed_demo.py
  tests/
    test_content.py       every step's URL reverses; statuses valid; 3 to 5 steps per role; eight roles
    test_views.py         landing, each journey and each prototype page return 200 for anonymous,
                          signed-in and staff users where appropriate; banner present on prototype pages
    test_seed_demo.py     seed_demo on an empty DB creates the expected platforms, uploads, annotations,
                          representations; running it twice does not duplicate
assets/scss/pages/_journeys.scss   styles (imported from main.scss with @use)
ddp_tracker/static/js/shortlist.js  only if needed (for example "copy link"); no inline scripts
```

Keep the prototype data in Python modules, not the database, so it is obviously fictional and easy to remove. The exception is data that the real app should hold, which `seed_demo` creates as real rows: platforms, uploads, annotations, representations.

## Shortlist behaviour (M3)

The simplest version that makes the hand-off tangible:

- **"Add to shortlist"** on M1 and M2 is a small form (POST) that stores the concept id in the session.
- **M3 lists them**, with their per-platform paths from the database.
- **"Download codebook (CSV)"** and **"Download DDM File Blueprint (JSON)"** return files generated from the shortlist, marked "prototype" in a header comment or field.

For the blueprint JSON, model the File Blueprint fields described in the DDM paper:

- a name;
- the expected file name or pattern (for example `user_data_tiktok.json`);
- required fields;
- the fields to keep.

This is illustrative, not the exact DDM import format; say so in the file.

If this grows too complex, fall back to static previews with fictional data. The session version is better if time allows.

## Design guidance

- **Match the current look:** `reference-screenshots/current-home.png` and `current-tiktok-explorer.png`. Clean, white, Bootstrap cards, dark navy primary colour, sans-serif.
- **The landing page must work on a phone:** cards stack, and nothing scrolls sideways.
- **Prototype banner:** use a Bootstrap `alert` in a warning or info tone, the same on every mock-up page (one include).
- **Status badges:** "Available" (success tone) and "Prototype" (secondary or warning tone). Use text, not only colour.
- **Accessibility:** one `h1` per page, logical heading order, link text that makes sense out of context, visible focus styles.
- **Language:** British English, no em dashes, plain words (the audience includes students and policy people).

## Decision log

Record every design decision you make that is not already in `02-decisions.md` (naming, layout, trade-offs, anything you dropped) in `DDP-Tracker-docs/handoff-user-journeys/09-build-decisions.md`, with the date and a one-line reason. Hekmat will review it.

## Acceptance criteria

1. `/` shows the landing page with eight role cards; each opens its journey.
2. Every journey has 3 to 5 steps, each with a status badge, and every link works.
3. Every prototype page shows the banner and fictional data, and is reachable from at least one journey.
4. The navigation matches `03-site-structure.md` (or the decision log explains differences), for anonymous, signed-in and staff users.
5. `uv run manage.py seed_demo` on a freshly migrated database produces:
   - three platforms and their uploads;
   - annotations and representations;
   - a second TikTok upload that shows as changed.

   Running it again does not duplicate anything.
6. All tests pass with `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest` and `uv run manage.py test`; coverage stays above 80%.
7. No inline scripts or styles anywhere in new templates (grep for `<script>` without `src` and for `style=`).
8. Existing pages and existing tests still work (tests changed only where the home page or navigation deliberately changed, and explained in the commit message).

## Delivery

Save to `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs`:

| What | Where |
|---|---|
| Git bundle of the branch | `bundles/user-journeys.bundle` |
| Screenshots (landing, every journey, every prototype page; desktop and one phone-width landing page) | `prototype-screenshots/` |
| How to push and run on Windows | `RUN-THE-PROTOTYPE.md` |
| Build decisions | `handoff-user-journeys/09-build-decisions.md` |
| Summary of what was built and what is left | `prototype-summary.md` |

Also:

- fetch the branch into Hekmat's local clone (`05-codebase-guide.md`, "Getting commits into Hekmat's repository");
- copy the Markdown files to the Project under `claude/`;
- update both README indexes.

`RUN-THE-PROTOTYPE.md` should cover:

- **Pushing:** `git push -u origin feat/user-journeys` from Windows (Git for Windows, GitHub Desktop or VS Code).
- **Running on Windows**, either:
  - Docker Desktop plus the upstream README's `just up` / docker compose route, then `seed_demo`; or
  - without Docker: install uv and Node, then run the commands from `05-codebase-guide.md` in PowerShell syntax (`$env:DATABASE_URL = "sqlite:///demo.sqlite3"` and so on).
- **Logging in** as the demo admin created by `seed_demo` (print its email and password when the command finishes; the password is only for local demos).
