# 00. Coordinator guide

You are the **coordinator** of the build. You do not write the application code yourself. You prepare the ground (Phase 0), give each implementation task to a fresh subagent, check what comes back, keep the ledger, talk to Hekmat at the check-ins, and deliver.

## 1. Before anything else

### 1.1 Read, in this order

1. `README.md` in this folder (what was verified, what changed since the handoff).
2. `01-design.md` (decisions, interfaces, rules).
3. `../handoff-user-journeys/00-START-HERE.md`, then `03-site-structure.md` and `04-user-journeys.md` there. Skim the rest of the handoff; it is background.
4. The repository's `AGENTS.md` and `CONTRIBUTING.md`.
5. `02-phase-0-setup.md`, and each phase file when you reach it.

### 1.2 Folders

You need to read and write in two places:

| What | Where |
|---|---|
| The repository (code only) | Your working directory. It is the local clone `C:\Users\hekma\Documents\Projects\DDP-Tracker` or a git worktree of it (then the path contains `.claude\worktrees\`). |
| Documents (never in the repository) | `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs` |

If writing to `DDP-Tracker-docs` is refused, ask Hekmat once to add that folder to the task, and wait.

### 1.3 Skills

If your environment offers the skill `superpowers:subagent-driven-development`, load it: section 3 below follows the same pattern, and this guide takes precedence where they differ. Subagents that write code should use `superpowers:test-driven-development` if they have it. Before you tell Hekmat that something works, run the check that proves it (`superpowers:verification-before-completion`).

## 2. Ground rules

1. **Writing style everywhere:** British English; never an em dash (use a comma, colon, semicolon or parentheses); plain words. It applies to code comments, templates, test names, commit messages, the ledger and your messages to Hekmat.
2. **Documents go to `DDP-Tracker-docs`, code goes to the repository.** Never the other way round. The screenshots tool and these plan files are documents.
3. **Commit, never push.** Hekmat pushes. Do not open pull requests.
4. **Additive changes only.** The existing files that may change are listed in `01-design.md`, 4.2. Existing tests must pass unchanged.
5. **One implementer at a time.** Subagents commit on the same branch in the same folder; two at once would collide. Reviewers only read, so a reviewer may run while you prepare the next brief.
6. **The plan's starter files are yours to copy.** `starter-files/` mirrors the repository's layout. They hold the designed content and data (journeys, demo specification, fictional data per mock-up, styles). They were formatted, linted and type-checked against the repository's rules, and the demo specification was run against the parser. Tasks say when to copy which file. Copy, do not retype.
7. **Small decisions are yours; record them.** Anything the plan does not fix (a wording, a layout detail, a name) you or a subagent may decide. Add a row to `../handoff-user-journeys/09-build-decisions.md` (date, decision, reason, decided by).
8. **Ask Hekmat before a big deviation:** dropping a page, changing a decision D1 to D38, touching an existing file that is not on the list, changing an existing test, adding a dependency.
9. **Stop conditions.** Stop and ask if: a gate fails twice for a reason you do not understand; `upstream/dev` has changed a file this plan touches in a way that contradicts it; anything would expose personal data.

## 3. How to assign a task

Every implementation task in the phase files has an id (for example 3.1), the files it owns, what it consumes and produces, the steps, and its acceptance checks. For each one:

### Step 1: brief a fresh subagent

Use the **Agent** tool with:

- `subagent_type`: `ddp-implementer`
- no `model`: the agent's definition sets the model (Opus) and the effort (high)
- `run_in_background`: `false` (the next step needs its result)
- `description`: the task id and three or four words, for example `Task 3.1 concept view`
- no `isolation` (the subagent must work in your folder, on the feature branch)

The agent already knows the standing rules, the gate, how to commit and how to report: they are in its definition (`agents/ddp-implementer.md` in this folder; installed in `C:\Users\hekma\.claude\agents\`). Read that file once, so that you know what it was told. Your brief only says which task:

```text
Repository (your working directory): <absolute path of your working directory>
Phase file: C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\implementation-plan\<phase file>
Your task: Task <id>: <title>

<Anything else it needs and cannot know: what an earlier task did differently from the plan,
a decision Hekmat made at a check-in, a finding to take into account. Leave out if nothing.>
```

Its report ends with STATUS, COMMITS, TESTS, GATE, DEVIATIONS, DECISIONS and QUESTIONS.

**If `ddp-implementer` is not among the agent types offered to you** (the definition was not installed, or was added after your session started): use `subagent_type: general-purpose` with `model: opus`, and put the whole text of `agents/ddp-implementer.md` below its front matter at the top of the brief. Tell Hekmat once that the subagents then run at the session's effort, not the pinned one. The same holds for the reviewer in step 3.

### Step 2: check the result yourself

Do not take the report on trust. Run:

```bash
git status --short                 # nothing uncommitted
git log --oneline -5               # the task's commits are there, with sensible messages
DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar 2>&1 | tail -4
```

Then the task's own "Acceptance" checks, and `git show --stat HEAD~<n>..HEAD` to see that only the task's files changed.

### Step 3: review

Each task says **Review: full** or **Review: light**.

- **Light:** you read the diff yourself (`git diff <before>..HEAD`). Look for: the required texts, no inline styles or scripts, no e-mail addresses shown, British English, no em dash.
- **Full:** give the task to a fresh reviewer: the Agent tool with `subagent_type: ddp-reviewer` and no `model` (its definition sets Opus at extra-high effort, and lets it read and run checks but not edit). Its definition, `agents/ddp-reviewer.md`, holds the two passes and the form of the report. Your brief:

  ```text
  Repository (your working directory): <absolute path>
  Phase file: C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\implementation-plan\<phase file>
  Task to review: Task <id>: <title>
  Its commits: <before>..<last>   (git diff <before>..<last>)

  <The implementer's DEVIATIONS and DECISIONS, quoted, if it reported any.>
  ```

  It answers with findings (must fix, should fix, note) and a verdict: APPROVED or CHANGES NEEDED.

### Step 4: fixes

Send "must fix" and "should fix" findings back to **the same implementer** with `SendMessage` (it still has the context), or to a fresh subagent with the findings and the task reference. Then check again (step 2). At most two rounds: after that, decide yourself or ask Hekmat.

### Step 5: ledger

Update `progress.md` (status, commits, notes) and add any decisions to `../handoff-user-journeys/09-build-decisions.md`. Then take the next task.

## 4. Commands (all verified on this computer)

Use the **Bash** tool (Git Bash). Run them from the repository folder unless stated.

| Purpose | Command |
|---|---|
| Install | `uv sync` |
| Tests with coverage | `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar` |
| One test file, fast | `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests/test_content.py -q -p no:sugar --no-cov` |
| Django's runner | `DJANGO_SETTINGS_MODULE=config.settings.cicd uv run manage.py test` |
| Lint and format | `uv run ruff check .` and `uv run ruff format .` |
| Types | `uv run mypy .` |
| Templates | `uv run djlint ddp_tracker/journeys --reformat`, then `uv run djlint ddp_tracker --check` |
| Hooks on staged files | `uv run pre-commit run` |
| CSS | `npm run build:css` (never `npm run build`: its second half fails on Windows) |
| Docs for `/docs/` | `uv run mkdocs build -q -f docs/mkdocs.yml` |
| Migrate a local database | `DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py migrate` |
| Demo data | `DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py seed_demo` |
| Run the site (in the background) | `DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend uv run manage.py runserver 127.0.0.1:8000` |
| Screenshots | from `DDP-Tracker-docs\implementation-plan\tools`: `uv run --no-project --with playwright python take_screenshots.py` |

Things to know:

- **Why `djlint ddp_tracker` and not `djlint .`:** once the docs are built, `docs/site/` holds HTML that djlint would report. CI does not build the docs, so `djlint .` passes there.
- **`demo.sqlite3`** is ignored by git (`*.sqlite3`). Delete it to start again.
- **Every test passes at the baseline,** because the branch starts with the parser fix (D37; `02-phase-0-setup.md`). A failing test is yours.
- **`manage.py` uses the local settings**, which need `USE_DOCKER` and a database: always set the variables as above, or `DJANGO_SETTINGS_MODULE=config.settings.cicd` for tests.
- **Line endings:** git converts them (`core.autocrlf=true`). A file that shows as modified with an empty `git diff` only differs in line endings: `git restore <file>`.
- **Stopping the server:** in PowerShell, `Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`.
- **The coverage floor is 80%** and the suite is at 97%. New code needs tests; do not lower the floor.

## 5. Gates

**Task gate** (the subagent runs it before committing, you run the tests again after): in `agents/ddp-implementer.md`, "The gate, before every commit".

**Phase gate** (you, at the end of each phase):

```bash
DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar 2>&1 | tail -4
DJANGO_SETTINGS_MODULE=config.settings.cicd uv run manage.py test 2>&1 | tail -4
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run djlint ddp_tracker --check
grep -rn "style=" ddp_tracker/journeys/templates ; grep -rn "<script" ddp_tracker/journeys/templates | grep -v "src="
grep -rn $'\u2014' ddp_tracker/journeys assets/scss/pages ; echo "(no output above means no em dash and no inline style or script)"
git status --short
```

From Phase 2 on, also run the site with a fresh database (`migrate`, `seed_demo`, `runserver`) and the screenshots tool: it fails if a page does not answer 200 or scrolls sideways at phone width.

## 6. Check-ins with Hekmat

At the end of **phases 2, 3 and 4**, before starting the next phase:

1. Run the screenshots tool and look at the pictures yourself first. Fix what is plainly broken.
2. Send Hekmat a short message: what is done, the screenshots that matter for this phase (send the files if your tools allow it, otherwise give their paths in `DDP-Tracker-docs\prototype-screenshots\`), what comes next, and one question: "Is there anything you want changed before I go on?"
3. Wait for the answer. Record what he decides in the decision log.

If Hekmat has told you to run without check-ins, skip the waiting, keep taking the screenshots, and list the open points in the final summary.

## 7. The tasks

"Owns" is what the task may create or change. A task never edits another task's files, except where stated.

| Id | Task | Who | Depends on | Owns | Review |
|---|---|---|---|---|---|
| 0.1 | Preflight: access, tools, git identity | You | | | |
| 0.2 | Branch and environment | You | 0.1 | | |
| 0.3 | Baseline, ledger, decision log | You | 0.2 | `progress.md`, the decision log | |
| 1.1 | App skeleton and fictional packages | Subagent | 0.3 | `journeys/__init__.py`, `apps.py`, `demo/__init__.py`, `demo/ddps.py`, `tests/__init__.py`, `tests/test_demo_ddps.py`, `LOCAL_APPS` in `config/settings/base.py` | Full |
| 1.2 | `seed_demo`: the command | Subagent | 1.1 | `demo/spec.py`, `demo/seed.py`, `management/**`, `tests/utils.py`, `tests/test_seed_demo.py` | Full |
| 2.1 | Journeys, routes and scaffolding | Subagent | 1.2 | `content.py`, `targets.py`, `feature_cards.py`, `views.py`, `urls.py`, `mockups/**` (copied), the templates of the landing page, the journeys and the frame, `tests/test_content.py`, `test_views.py`, `test_mockups.py`, `test_conventions.py`; `config/urls.py`, `core/urls.py`, two lines in `config/settings/base.py` | Full |
| 2.2 | Navigation and styles | Subagent | 2.1 | `templates/base.html`, `journeys/_prototype_nav.html`, `assets/scss/pages/_journeys.scss`, `assets/scss/main.scss`, `static/css/main.css`, `static/js/journeys.js`, additions to `tests/test_views.py` | Full |
| 2.3 | Screenshots and check-in | You | 2.2 | `prototype-screenshots/` | |
| 3.1 | Concept view (M1) | Subagent | 2.2 | `mockups/concepts.py`, `prototype/concepts.html`, `tests/test_concepts.py` | Full |
| 3.2 | Concept detail (M2) | Subagent | 3.1 | `mockups/concepts.py`, `prototype/concept.html`, `tests/test_concepts.py` | Light |
| 3.3 | Shortlist and exports (M3) | Subagent | 3.2 | `mockups/shortlist.py`, `prototype/shortlist.html`, `tests/test_shortlist.py`; the "Add to shortlist" forms in `concepts.html` and `concept.html` | Full |
| 3.4 | Changelog (M5) | Subagent | 2.2 | `mockups/changes.py`, `prototype/changes.html`, `tests/test_changes.py` | Full |
| 3.5 | API overview (M6) | Subagent | 2.2 | `mockups/api.py`, `prototype/api.html`, `tests/test_api.py` | Light |
| 3.6 | Screenshots and check-in | You | 3.1 to 3.5 | | |
| 4.1 | Compare (M4) | Subagent | 3.1 | `mockups/compare.py`, `prototype/compare.html`, `tests/test_compare.py` | Light |
| 4.2 | Snapshots (M7) | Subagent | 2.2 | `mockups/snapshots.py`, `prototype/snapshots.html`, `tests/test_snapshots.py` | Light |
| 4.3 | Request instructions (M8) | Subagent | 2.2 | `mockups/instructions.py`, `prototype/request.html`, `tests/test_instructions.py` | Light |
| 4.4 | Moderator dashboard (M9) | Subagent | 2.2 | `mockups/moderate.py`, `prototype/moderate.html`, `tests/test_moderate.py` | Full |
| 4.5 | Seed annotations (M10) | Subagent | 2.2 | `mockups/seeding.py`, `prototype/seed.html`, `tests/test_seeding.py` | Light |
| 4.6 | Roles and platforms (M11) | Subagent | 2.2 | `mockups/roles.py`, `prototype/roles.html`, `tests/test_roles.py` | Light |
| 4.7 | Learn (M12) | Subagent | 2.2 | `mockups/learn.py`, `prototype/learn.html`, `tests/test_learn.py` | Light |
| 4.8 | Feature cards page | Subagent | 2.2 | `views.py` (the `features` view), `features.html`, `tests/test_feature_cards.py` | Light |
| 4.9 | Screenshots and check-in | You | 4.1 to 4.8 | | |
| 5.1 | Accessibility and phone width | Subagent | 4.9 | Templates and `_journeys.scss` of the app, `main.css` | Full |
| 5.2 | Rebase on upstream and full gate | You | 5.1 | | |
| 5.3 | Final screenshots | You | 5.2 | `prototype-screenshots/` | |
| 5.4 | Documents | You | 5.3 | `RUN-THE-PROTOTYPE.md`, `prototype-summary.md`, the decision log, `README.md` of `DDP-Tracker-docs` | |
| 5.5 | Handover | You | 5.4 | | |

All paths under "Owns" that start with `journeys/`, `demo/`, `mockups/`, `management/`, `tests/` or `prototype/` are inside `ddp_tracker/journeys/` (templates inside `ddp_tracker/journeys/templates/journeys/`).

Order: strictly by id. Tasks 3.4, 3.5 and 4.2 to 4.8 do not depend on each other, so if one is blocked you may take the next and come back.

## 8. When something goes wrong

| Situation | What to do |
|---|---|
| A subagent reports BLOCKED | Read its question. If the plan answers it, answer and continue the same subagent with `SendMessage`. If not, decide (small) or ask Hekmat (big). |
| A starter file does not fit (an import fails, a name differs) | The plan is wrong there, not the repository. Let the subagent adapt the copy, note it as a deviation, and record it in the ledger. |
| A test of the plan asserts something the implementation words differently | The acceptance checks are the contract for behaviour, not for every word. A subagent may change a test's wording check if it keeps its meaning, and must say so under DEVIATIONS. |
| An existing test fails | Stop the task. It means an existing file changed in a way the plan did not intend. Find the cause before anything else. |
| `upstream/dev` moved (Phase 0 or Phase 5) | See `02-phase-0-setup.md`, "If upstream has moved", and `07-phase-5-polish-and-delivery.md`, task 5.2. |
| `uv run pre-commit run` cannot download its hooks | Note it in the ledger and rely on the task gate (ruff, mypy, djlint) for that commit. |
| A commit fails with "Author identity unknown" | Phase 0.1 was skipped: ask Hekmat for the name and e-mail address to commit with. |

## 9. If time runs short

Twelve mock-ups are a lot. The order of the phases is the order of importance: phases 1 to 3 are the core ("two views, one model, and a hand-off"). In Phase 4 every page already exists as a placeholder with the banner, so the prototype is whole at any point. If Hekmat asks you to cut, keep 4.1 (compare), 4.4 (dashboard) and 4.5 (seeding), make the others static pages from their starter data, and record the trade-off in the decision log.

## 10. What "done" means

All of `../handoff-user-journeys/00-START-HERE.md`, "Definition of done", with these differences: no bundle, and the branch is in the local clone already (D19); no copies in the Claude Project (D38). Task 5.5 has the closing checklist.
