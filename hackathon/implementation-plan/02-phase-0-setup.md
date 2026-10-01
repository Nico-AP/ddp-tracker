# 02. Phase 0: set-up

The coordinator does this phase itself. Output: a working environment on the branch `feat/user-journeys`, a known baseline, the ledger and the decision log started. Nothing is committed in this phase.

## Task 0.1: Preflight

- [ ] **Folders.** Confirm that you can read `AGENTS.md` in your working directory and list `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs`. Open `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\implementation-plan\progress.md` and set "Started" to today's date: if that write is refused, ask Hekmat to add the folder to the task.

- [ ] **Subagents.** Check that `ddp-implementer` and `ddp-reviewer` are among the agent types your Agent tool offers. They pin the subagents' model and effort, and they were written on 30 September 2026 without a chance to test that they load (the planning task's own session had started before they existed). If they are missing, read `00-coordinator-guide.md`, section 3, "If `ddp-implementer` is not among the agent types offered to you", and tell Hekmat in your Phase 0 report. Note in `progress.md` which way you work.

- [ ] **Tools.**

  ```bash
  uv --version && node --version && npm --version && git --version
  ```

  Expected: uv 0.11 or later, Node 20 or later, any recent npm and git. If uv or Node is missing, ask Hekmat to install it; do not install system software yourself.

- [ ] **Git identity.**

  ```bash
  git config user.name; git config user.email
  ```

  On 30 September 2026 both were empty on this computer, and a commit fails without them. If they are still empty, ask Hekmat one question: "Which name and e-mail address should the commits carry?" Then set them for this repository only:

  ```bash
  git config user.name "<the name he gave>"
  git config user.email "<the address he gave>"
  ```

  Do not guess, and do not set them globally.

- [ ] **Where you are.**

  ```bash
  pwd && git rev-parse --abbrev-ref HEAD && git status --short && git worktree list
  ```

  The status must be empty. If it is not, ask Hekmat before going on: do not stash or discard someone else's changes.

## Task 0.2: Branch and environment

- [ ] **Fetch upstream and create the branch** from the latest `upstream/dev`:

  ```bash
  git fetch upstream
  git log --oneline -1 upstream/dev
  git switch -c feat/user-journeys --no-track upstream/dev
  ```

- [ ] **Bring in the parser fix** (D37). The local branch `fix/parser-mime-registry` holds one commit that makes two parser tests pass on Windows. Hekmat wants the prototype branch to have it from the start, so that the suite is green here. It becomes the branch's first commit:

  ```bash
  git cherry upstream/dev fix/parser-mime-registry
  ```

  - A line that starts with `+`: upstream does not have the fix yet. Pick it: `git cherry-pick fix/parser-mime-registry`.
  - A line that starts with `-`, or no output: upstream has it already. Do nothing.
  - "unknown revision": the branch is missing from this clone. Tell Hekmat, and go on without it: the two tests `packages/ddp-parser/tests/test_pipeline.py::WorkedExampleTests` then fail on Windows, which is known and not the prototype's (note it in `progress.md` and treat those two as the baseline).

  This is the only change to the parser on this branch. No task touches it.

  If the branch exists already (a build that was interrupted): `git switch feat/user-journeys`, read `progress.md`, and resume at the first task that is not done.

  If git says the branch is checked out in another worktree, that worktree belongs to an earlier task: tell Hekmat and ask whether to continue there.

- [ ] **If upstream has moved** (the first line of `git log` above is not `a18b3f3`), look at what changed in the files this plan depends on:

  ```bash
  git diff --stat a18b3f3 upstream/dev -- config ddp_tracker/templates/base.html ddp_tracker/core assets/scss ddp_tracker/ddps ddp_tracker/schemas ddp_tracker/reviews ddp_tracker/representations ddp_tracker/proposals ddp_tracker/annotations packages/ddp-parser/src
  ```

  Read the diff of anything listed. What matters:

  | If this changed | Then |
  |---|---|
  | `templates/base.html`, `core/urls.py`, `core/templates/core/index.html`, `core/tests/tests.py` | Re-read task 2.1 and 2.2 against the new files before briefing them. |
  | A function in `01-design.md`, table 5.6 (name or arguments) | Note the new form in the ledger and tell the subagents of tasks 1.2, 3.x and 4.x. |
  | The parser (`packages/ddp-parser/src`) | The paths in `starter-files/.../demo/spec.py` may differ. Task 1.2's tests will show it: `seed_demo` stops with a clear message that names the missing path. |
  | Migrations of the vocabulary (`representations/migrations`) | Check that the slugs `user`, `viewed`, `searched`, `responded`, `followed`, `created`, `video`, `object`, `image`, `profile`, `note`, `when`, `identifier`, `value`, `name` still exist. |

  Write what you found under "Upstream" in `progress.md`.

- [ ] **Install and build.**

  ```bash
  uv sync
  npm ci
  npm run build:css
  git status --short
  ```

  Expected: no changes. If `ddp_tracker/static/css/main.css` shows as modified and `git diff` prints nothing but a line-ending notice, run `git restore ddp_tracker/static/css/main.css`. If the diff is real, upstream changed the Sass without rebuilding: leave it, and mention it in the ledger (task 2.2 will rebuild anyway).

- [ ] **Build the docs**, so that `/docs/` works locally (the contributor's journey links to the privacy guide):

  ```bash
  uv run mkdocs build -q -f docs/mkdocs.yml
  ```

  `docs/site/` is ignored by git.

## Task 0.3: Baseline, ledger, decision log

- [ ] **Run the baseline** and compare with `README.md`, "What was verified":

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar 2>&1 | tail -6
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run manage.py test 2>&1 | tail -4
  uv run ruff check . && uv run ruff format --check .
  uv run mypy .
  uv run djlint ddp_tracker --check
  ```

  Expected at `a18b3f3` plus the parser fix: 493 passed and none failed, coverage 97%; 261 tests OK with Django's runner; ruff, mypy and djlint clean. (Without the fix: 490 passed and 2 failed, both in `packages/ddp-parser/tests/test_pipeline.py::WorkedExampleTests`.) Write the numbers you get into `progress.md` under "Baseline". They are what every later gate is compared with.

  If anything else fails before you have changed a file, stop and tell Hekmat: the plan assumes a green start.

- [ ] **Check that the site runs**, once:

  ```bash
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py migrate -v 0
  ```

  Then start the server in the background (command in `00-coordinator-guide.md`, section 4), open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/platforms/` (both answer 200; the platform list is empty), and stop the server.

- [ ] **Start the decision log.** Open `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\handoff-user-journeys\09-build-decisions.md` and add one row per decision D19 to D38 from `01-design.md`, section 2: the date 30 September 2026, the decision and the reason as written there, and "Planning task; to be confirmed by Hekmat" in the last column. Remove the empty row.

- [ ] **Tell Hekmat, briefly,** that Phase 0 is done: the branch, the baseline numbers, anything that differed from the plan. Do not wait for an answer; go on with Phase 1.
