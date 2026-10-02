# Implementation plan: user journeys prototype

Written 30 September 2026 for Hekmat Alrouh (infrastructure track, DDP2026 Hackathon) by the planning task. It turns the handoff in `../handoff-user-journeys/` and the latest hackathon document into a plan that another task can carry out from start to finish.

**Nothing in this folder has been built yet.** The planning task only read, designed and verified assumptions (see "What was verified").

## How to use this folder

1. Hekmat starts a new Claude Code task in the `DDP-Tracker` project with the model Opus 5.5 and pastes the prompt in `coordinator-prompt.md`.
2. That task is the **coordinator**. It reads `00-coordinator-guide.md`, then works through the phases, giving each implementation task to a fresh subagent.
3. The coordinator keeps `progress.md` up to date, so a later task can resume.

## Files

| # | File | What it holds | Who reads it |
|---|---|---|---|
| | `README.md` | This overview | Everyone |
| | `coordinator-prompt.md` | The prompt that starts the build | Hekmat |
| 00 | `00-coordinator-guide.md` | How the coordinator works: set-up, how to assign tasks, review gates, check-ins, the task list | Coordinator |
| 01 | `01-design.md` | The design: new decisions, features drawn from the hackathon notes, architecture, the shared interfaces, the look | Coordinator and every subagent |
| 02 | `02-phase-0-setup.md` | Phase 0: access, branch, environment, baseline (tasks 0.1 to 0.3) | Coordinator |
| 03 | `03-phase-1-demo-data.md` | Phase 1: the fictional packages and `seed_demo` (tasks 1.1 and 1.2) | Subagents |
| 04 | `04-phase-2-landing-and-journeys.md` | Phase 2: landing page, journeys, scaffolding, navigation, styles (tasks 2.1 to 2.3) | Subagents, coordinator |
| 05 | `05-phase-3-core-mockups.md` | Phase 3: mock-ups M1, M2, M3, M5, M6 (tasks 3.1 to 3.6) | Subagents, coordinator |
| 06 | `06-phase-4-remaining-mockups.md` | Phase 4: mock-ups M4, M7 to M12 and the feature cards page (tasks 4.1 to 4.9) | Subagents, coordinator |
| 07 | `07-phase-5-polish-and-delivery.md` | Phase 5: accessibility, rebase, screenshots, documents, handover (tasks 5.1 to 5.5) | Coordinator and one subagent |
| | `progress.md` | The ledger: one row per task, filled in during the build | Coordinator |
| | `starter-files/` | Files the build copies into the repository as they are: the designed content and data (see its `README.md`) | Subagents |
| | `agents/` | The two subagent definitions, `ddp-implementer` and `ddp-reviewer`: their model, effort and standing rules. They are installed in the `.claude\agents` folder of Hekmat's user profile; these are copies to read | Coordinator |
| | `tools/take_screenshots.py` | Takes the screenshots and checks each page while doing so | Coordinator |
| | `planning-screenshots/` | What the landing page, two journeys and the concept view looked like when the plan's listings were run while planning: the look to aim for | Coordinator, subagents of tasks 2.2 and 3.1 |

28 tasks in all: 10 for the coordinator, 18 for subagents.

## How the work is assigned, in short

One coordinator (the task Hekmat starts, on Opus 5.5 at high effort), which does not write application code. For each implementation task it starts a fresh subagent of the type `ddp-implementer` (Opus, high effort), one at a time, with a short brief that names the task's section in a phase file. When the subagent reports, the coordinator runs the checks itself, has the work reviewed (by itself for small pages; by a fresh `ddp-reviewer` subagent, Opus at extra-high effort and read-only, for the load-bearing tasks), has findings fixed, and writes the result into `progress.md`. It stops for Hekmat at the end of phases 2, 3 and 4 with screenshots. The details are in `00-coordinator-guide.md`.

The handoff files stay the source for background: `../handoff-user-journeys/00-START-HERE.md` to `09-build-decisions.md`, `../DDP-Tracker_features-by-role.md` and `../sample-ddps/README.md`. Where this plan and the handoff differ, **this plan wins** (the differences are listed as decisions D19 to D38 in `01-design.md`).

## What changed since the handoff was written

The handoff assumed a build in a cloud container, delivered as a git bundle. The build will instead run in Claude Code on Hekmat's Windows computer, directly in the local clone. That changes the set-up and the delivery, not the product.

The hackathon document also moved on. The plan uses its latest version (`../latest hackathon google doc.docx`), in particular the notes under the Infrastructure Track heading: the core questions on user journeys, seeding annotations, the time zone and paired donation feature cards, governance, and the new items in the outcomes list.

## What was verified while planning (30 September 2026, on Hekmat's computer)

These are facts, checked by running them in a scratch copy of the repository at commit `a18b3f3`. Nothing was committed.

| Check | Result |
|---|---|
| `uv sync` | Works (uv 0.11.16 fetches Python 3.14 itself) |
| Tests, `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar` | 490 passed, **2 failed**, coverage 97%. The two failures are in the parser package (`packages/ddp-parser/tests/test_pipeline.py::WorkedExampleTests::test_from_bytes` and `::test_from_path_and_stream`). They only fail on Windows: the Windows registry maps `.csv` to `application/vnd.ms-excel`. A fix exists as one commit on its own branch, `fix/parser-mime-registry` (from `upstream/dev`, not pushed, to offer to Nico by itself). On Hekmat's wish the prototype branch also starts with that commit (decision D37; Phase 0 picks it), so the build's baseline is **493 passed and none failed**. No task of the build touches the parser. |
| Tests, `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run manage.py test` | 261 tests, OK |
| `npm ci` | Works |
| `npm run build:css` | Works, and rebuilding the untouched Sass gives a byte-identical `main.css` |
| `npm run build` | **Fails on Windows** at `build:vendor` (`mkdir -p`, `cp`). Not needed: the vendor files are committed. Use `npm run build:css`. |
| Compiled CSS | `ddp_tracker/static/css/main.css` **is committed upstream**, in the same commit as each Sass change (unlike what `AGENTS.md` says). Do the same. |
| Local run on SQLite | `migrate`, `check` and `runserver` work with `DATABASE_URL=sqlite:///…`, `USE_DOCKER=no`. `/docs/` gives 404 until `uv run mkdocs build -f docs/mkdocs.yml` has run. |
| Git identity | **Not configured** on this computer (`git commit` fails with "Author identity unknown"). Phase 0 asks Hekmat. |
| Pre-commit hook | Not installed in the clone. The plan runs the hooks by hand and does not install the hook. |
| Screenshots | Playwright drives the installed Microsoft Edge without downloading a browser: `uv run --no-project --with playwright python script.py` with `launch(channel="msedge")`. |
| Sample DDP paths | Every path that the demo data annotates exists after parsing (listed in `03-phase-1-demo-data.md`). |
| Demo data flow | Creating an `Upload`, writing the zip to the incoming folder, `parse_upload.call(...)`, then `checks.approve(...)` registers an upload in about 0.2 seconds. With the planned March TikTok package uploaded first, the September one passes the plausibility check by itself (similarity 0.97) and its review shows 38 new data points (33 of them recognised as moved), 1 changed and, once annotated, 1 missing. |
| Fictional YouTube package | Parses (watch history, search history, subscriptions as CSV). |
| Lint and types at the baseline | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` and `uv run djlint . --check` are clean. After the docs are built, `djlint .` also reads `docs/site/` and reports 12 files: use `uv run djlint ddp_tracker --check`. |
| The starter files | Formatted, linted and type-checked with the repository's rules. `demo/spec.py` and `demo/seed.py` were run against an in-memory database: a first run creates 2 users, 4 platforms, 5 uploads, 28 annotations, 9 representations, 21 example values, 1 suggested term and 1 suggestion; a second run creates nothing; `reset()` leaves nothing. The Sass partial compiles. |
| The queries of the mock-up pages | Run against that seeded database: the TikTok changelog gives 5 added, 33 moved, 1 changed, 1 removed; TikTok has 190 data points, 177 without an annotation; all platforms together 632. The tests in the phase files use these figures. |
| The listings of phases 1 and 2 | Extracted from the phase files by a script and run in a scratch copy (with a stand-in for `demo/ddps.py`): the command, `targets.py`, `views.py`, `urls.py`, every template and the four test files. 62 tests passed; the whole suite stayed at the baseline plus the new tests (552 passed, the 2 known failures), with every existing test unchanged; ruff and mypy clean. `seed_demo` printed exactly what task 1.2 expects. |
| The listings of phases 3 and 4 | The view code of every mock-up and the concept view's template were extracted and run the same way. All tests of task 3.1 passed, as did the tests of the exports and of the changelog's computation, and the figures that the other tests assert on the views' contexts. |
| The look | The landing page, two journeys and the concept view were rendered from the listings and the starter stylesheet, wide and at 375 pixels: see `planning-screenshots/`. Nothing scrolled sideways. One thing was changed after looking: secondary buttons use `btn-secondary`, because `btn-outline-secondary` was too pale to read. |

The scratch copy was deleted afterwards. Nothing was committed, and the repository is as it was.

## What was not verified

- `demo/ddps.py` (task 1.1) is described, not written: the checks used a stand-in that loads the generator in `sample-ddps/`.
- The templates of tasks 3.2 to 4.8 are specified in words, so the tests that look for their texts have not run. Where a test and a page disagree on a wording, the build adjusts the wording check and notes it (`00-coordinator-guide.md`, section 8).
- The accessibility tests (task 5.1) ran only against the pages that existed in the check.
- The Docker route in the run instructions was not tried.
- Nothing was tried on PostgreSQL (CI runs the suite there as well).
