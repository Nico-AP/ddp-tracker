# 07. Phase 5: polish and delivery

Output: the prototype is checked for accessibility and phone width, sits on the latest `upstream/dev`, passes every gate, and is handed to Hekmat with screenshots and the documents he needs to push and run it.

---

## Task 5.1: Accessibility and phone width

**Review:** full.

The coordinator prepares this task; a subagent carries it out.

**Coordinator, before the brief:**

- [ ] Fresh database, seed, server, screenshots tool. Collect its PROBLEM lines (a page that scrolls sideways at 375 pixels, a page that does not answer 200).
- [ ] Look at every screenshot yourself, the phone ones first. Write down what is off: text that overflows, a table that is cut, a button row that does not wrap, a heading that looks out of order, two badges that touch, a page that reads badly. Keep the list concrete: page, what, where.
- [ ] Add what Hekmat asked for at the check-ins and has not been done yet.
- [ ] Put the list into the subagent's brief, under "Findings to fix".

**Files (subagent):**

- Create: `ddp_tracker/journeys/tests/test_accessibility.py`
- Modify: templates under `ddp_tracker/journeys/templates/journeys/`, `assets/scss/pages/_journeys.scss`, and then `ddp_tracker/static/css/main.css` (rebuilt)

- [ ] **Step 1: Write the tests** (they state the rules of `01-design.md`, section 7, for every page of the app)

  `ddp_tracker/journeys/tests/test_accessibility.py`:

  ```python
  """What every page of the app must get right for people who use a keyboard or a screen
  reader: one main heading, headings in order, tables with header cells, fields with labels,
  links and buttons with text. Checked on the rendered pages, with the demo data."""

  from html.parser import HTMLParser

  from django.urls import reverse

  from ddp_tracker.journeys.content import ROLES
  from ddp_tracker.journeys.tests.test_mockups import mockup_urls
  from ddp_tracker.journeys.tests.utils import SeededTestCase

  VOID = {"input", "img", "br", "hr", "meta", "link"}


  class Outline(HTMLParser):
      """What the checks need from a page: its headings, tables, form fields and labels, and
      the links and buttons that have no text."""

      def __init__(self):
          super().__init__()
          self.headings = []  # levels, in order
          self.tables = 0
          self.header_cells = 0  # th with a scope
          self.fields = []  # ids of visible inputs, selects and textareas ("" if none)
          self.labels = set()  # the ids that labels are for
          self.unnamed = []  # links and buttons without text or an aria-label
          self._open = []  # [tag, has a name] of the links and buttons we are inside

      def handle_starttag(self, tag, attrs):
          found = dict(attrs)
          if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
              self.headings.append(int(tag[1]))
          elif tag == "table":
              self.tables += 1
          elif tag == "th" and found.get("scope") in {"col", "row"}:
              self.header_cells += 1
          elif tag == "label":
              self.labels.add(found.get("for", ""))
          elif tag in {"select", "textarea"} or (
              tag == "input" and found.get("type") not in {"hidden", "submit", "button"}
          ):
              self.fields.append(found.get("id", "") if "aria-label" not in found else None)
          if tag in {"a", "button"}:
              self._open.append([tag, bool(found.get("aria-label"))])

      def handle_data(self, data):
          if self._open and data.strip():
              self._open[-1][1] = True

      def handle_endtag(self, tag):
          if tag in {"a", "button"} and self._open:
              opened, named = self._open.pop()
              if not named:
                  self.unnamed.append(opened)


  def pages():
      urls = {"landing": "/", "features": reverse("journeys:features")}
      urls |= {
          f"journey {role.slug}": reverse("journeys:journey", args=[role.slug]) for role in ROLES
      }
      urls |= {f"mock-up {key}": url for key, url in mockup_urls().items()}
      urls["shortlist with concepts"] = reverse("journeys:shortlist") + "?c=watched-video&c=searched"
      urls["seed pairs"] = reverse("journeys:seed") + "?source=pairs"
      urls["seed ai"] = reverse("journeys:seed") + "?source=ai"
      return urls


  class AccessibilityTests(SeededTestCase):
      def outlines(self):
          for name, url in pages().items():
              response = self.client.get(url)
              self.assertEqual(response.status_code, 200, name)
              outline = Outline()
              outline.feed(response.content.decode())
              yield name, outline

      def test_one_main_heading_and_no_skipped_level(self):
          for name, outline in self.outlines():
              with self.subTest(page=name):
                  self.assertEqual(outline.headings.count(1), 1)
                  self.assertEqual(outline.headings[0], 1)
                  for before, after in zip(outline.headings, outline.headings[1:], strict=False):
                      self.assertLessEqual(after, before + 1, outline.headings)

      def test_tables_have_header_cells(self):
          for name, outline in self.outlines():
              with self.subTest(page=name):
                  if outline.tables:
                      self.assertGreaterEqual(outline.header_cells, outline.tables)

      def test_fields_have_labels(self):
          for name, outline in self.outlines():
              with self.subTest(page=name):
                  for field in outline.fields:
                      if field is not None:  # None: it has an aria-label
                          self.assertIn(field, outline.labels - {""})

      def test_links_and_buttons_have_text(self):
          for name, outline in self.outlines():
              with self.subTest(page=name):
                  self.assertEqual(outline.unnamed, [])
  ```

  A generator that yields inside a loop is fine here because the `subTest` is opened by the caller, not inside the generator.

  The header of `base.html` is part of every page: its brand link holds an image with an empty `alt` and the text "DDP Tracker", so it has a name. If an existing page element fails a check, do not change `base.html`: narrow the check to the page's `<main>` (feed the parser only the part between `<main` and `</main>`), and say so in your report.

- [ ] **Step 2: Run them.** Fix what they find in the templates. Typical fixes: an `h3` directly under an `h1` (add the `h2`, or make it an `h2`); an `<input>` without `id` and `<label for>`; a table without `<th scope="col">`; two buttons that both read "Remove" (name what they remove; a `visually-hidden` span is fine).

- [ ] **Step 3: Fix the coordinator's findings,** one by one. Layout fixes go into `_journeys.scss` (then `npm run build:css`). Keep to the classes of the design; do not restyle existing pages.

- [ ] **Step 4: Read every page's text once more** for the writing rules: British English, no em dash, plain words, sentences that a student or a policy officer can follow. Check that every figure, name or text that is made up carries the fictional label where it stands next to real data.

- [ ] **Step 5: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys assets/scss ddp_tracker/static/css/main.css
  uv run pre-commit run
  git commit -m "fix(journeys): headings, labels and narrow screens across the prototype pages"
  ```

**Acceptance:** the four accessibility tests pass on all pages; the screenshots tool, run again by the coordinator, prints no PROBLEM line; every finding of the brief is fixed or answered.

---

## Task 5.2: Rebase on upstream and the full gate (coordinator)

- [ ] **Fetch and compare.**

  ```bash
  git fetch upstream
  git log --oneline HEAD..upstream/dev | head -20
  ```

  No output: upstream has not moved; skip to the gate.

- [ ] **Rebase.**

  ```bash
  git rebase upstream/dev
  ```

  Where conflicts are likely, and what to do:

  | File | Resolution |
  |---|---|
  | `ddp_tracker/static/css/main.css` | Never merge it by hand. Take either side (`git checkout --theirs ddp_tracker/static/css/main.css`), finish resolving the Sass, run `npm run build:css`, then `git add` it. |
  | `assets/scss/main.scss` | Keep upstream's lines and our one `@use "pages/journeys";` line at the end. |
  | `ddp_tracker/templates/base.html` | Take upstream's version and re-apply our three edits (task 2.2, step 3). Then re-read the list "Existing tests that look at the header" in task 2.2. |
  | `config/settings/base.py`, `config/urls.py`, `ddp_tracker/core/urls.py` | Keep upstream's changes and our lines. |
  | The parser fix (the branch's first commit, `packages/ddp-parser/…/mime.py` and `tests/test_source.py`) | If Nico has merged the same change, git drops our copy during the rebase by itself. If it stops there with a conflict or an empty commit, upstream has the fix in another form: `git rebase --skip`. |

  If upstream changed the home page or the navigation in a way that contradicts D20 or D21, or the rebase gets confusing: `git rebase --abort`, and ask Hekmat how to proceed (the alternative is to deliver on the base the branch has, and note it).

- [ ] **If the parser or the models changed upstream,** run the seeding tests first (`ddp_tracker/journeys/tests/test_seed_demo.py`): a changed path shows up there with a clear message.

- [ ] **The full gate** (`00-coordinator-guide.md`, section 5, "Phase gate"), and the acceptance criteria of the handoff (`../handoff-user-journeys/06-build-plan.md`, "Acceptance criteria"), one by one:

  | # | Criterion | How to check |
  |---|---|---|
  | 1 | `/` shows eight role cards; each opens its journey | `test_views.py`; by hand |
  | 2 | Every journey has 3 to 5 steps with a badge; every link works | `test_content.py`; the walk of task 4.9 |
  | 3 | Every prototype page has the banner and is reached from a journey | `test_mockups.py` |
  | 4 | The navigation matches the site structure, or the decision log explains the difference | D21 in the decision log; `NavigationTests` |
  | 5 | `seed_demo` on a fresh database gives the demo; a second run adds nothing | `test_seed_demo.py`; by hand on a new `demo.sqlite3` |
  | 6 | Both test runners pass; coverage above 80% | The gate: every test passes (the branch carries the parser fix, D37). |
  | 7 | No inline script or style in the new templates | `test_conventions.py`; the two `grep` lines of the gate |
  | 8 | Existing pages and tests still work; no existing test was changed | `git diff upstream/dev --stat -- '*tests*' ':!ddp_tracker/journeys'` prints nothing but `packages/ddp-parser/tests/test_source.py`, which the parser fix extends by one test (or nothing at all, once upstream has the fix) |

- [ ] **Look at the history.** `git log --oneline upstream/dev..HEAD`: small commits, imperative subjects with a prefix, British English, no em dash. Do not rewrite history to make it prettier unless a message breaks a rule.

---

## Task 5.3: Final screenshots (coordinator)

- [ ] Empty `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\prototype-screenshots\` of earlier pictures (they are yours, from the check-ins).
- [ ] Fresh database (`rm -f demo.sqlite3`, `migrate`, `seed_demo`), server, then the tool. Expected: the landing page (wide and phone), eight journeys, every mock-up page (the seeding page three times), the feature cards, the overview, the explorer, and five pictures as staff. No PROBLEM line.
- [ ] Add by hand, with the browser pane or by extending the tool's lists, what the tool does not cover and the summary should show: the review of the September TikTok upload (as the demo admin, from the contributor's journey), and the inspection of the held YouTube upload (as the demo curator).
- [ ] Stop the server.

---

## Task 5.4: Documents (coordinator)

All in `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs`. British English, no em dash.

- [ ] **`RUN-THE-PROTOTYPE.md`.** For Hekmat, on Windows. Contents, in this order:

  1. **What this is:** two sentences, and the branch name.
  2. **Push the branch** (the task could not): in PowerShell or Git Bash, from `C:\Users\hekma\Documents\Projects\DDP-Tracker`:

     ```powershell
     git push -u origin feat/user-journeys
     ```

     GitHub Desktop or VS Code work as well. No pull request is opened; whether to offer the work to Nico is an open question.
  3. **Run it without Docker** (verified on this computer). Node is not needed: the compiled CSS is in the repository.

     ```powershell
     cd C:\Users\hekma\Documents\Projects\DDP-Tracker
     git switch feat/user-journeys
     uv sync
     $env:DATABASE_URL = "sqlite:///demo.sqlite3"
     $env:USE_DOCKER = "no"
     $env:DJANGO_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
     uv run manage.py migrate
     uv run manage.py seed_demo
     uv run mkdocs build -q -f docs/mkdocs.yml
     uv run manage.py runserver
     ```

     Then open http://127.0.0.1:8000/. The `mkdocs` line is optional: without it the Docs link and the privacy guide give "not found". The three `$env:` lines are needed in every new PowerShell window.
  4. **Run it with Docker** (the upstream way): `npm install`, `npm run build:css`, `docker compose -f docker-compose.local.yml up -d --build`, then `docker compose -f docker-compose.local.yml run --rm django python manage.py seed_demo`. Say that this route was not tested by the build.
  5. **Log in:** the two demo users and the password that `seed_demo` prints (from `demo/spec.py`), what each can do, and that the password only exists when `DEBUG` is on.
  6. **A five-minute tour:** the landing page; the researcher's journey to the shortlist; "copy the link", then the engineer's journey; the TikTok changelog; as the demo admin, Approvals (approve the YouTube upload and watch YouTube appear under Explore).
  7. **Start again:** `uv run manage.py seed_demo --reset`, or delete `demo.sqlite3` and migrate again.
  8. **If something is off:** a port in use; unstyled pages (the branch was not checked out); `/docs/` not found (build the docs).

- [ ] **`prototype-summary.md`.** What was built, for the team as much as for Hekmat:

  1. What it is and where (branch, commits from `upstream/dev` to the tip, the number of tests added).
  2. The pages: a table with the URL, whether it is real or a mock-up, which journeys use it, and its screenshot's file name.
  3. What is real in the mock-ups (computed from the demo data) and what is fictional.
  4. What came from the hackathon notes (the table of `implementation-plan/01-design.md`, section 3, brought up to date with what was built).
  5. The decisions to confirm: D19 to D38 and those made during the build, with the two most visible first (the home page and the prototype strip).
  6. What is left and what was cut, honestly: anything simplified, any known rough edge.
  7. Findings on the way that are not the prototype's to fix: two parser tests failed on Windows (`.csv` is `application/vnd.ms-excel` in the Windows registry), for which a fix sits on the branch `fix/parser-mime-registry` and as the first commit of the prototype branch, ready to offer to Nico as its own pull request; `npm run build` failing on Windows (`mkdir -p`, `cp`), `AGENTS.md` saying that `main.css` is not committed while it is, and anything else you met. These are worth reporting to Nico.
  8. Open questions for the track (from `../handoff-user-journeys/08-known-issues-and-open-questions.md`, plus: data logs as data donations; whether AI-suggested labels may be public before a check; the licence).

- [ ] **The decision log** (`handoff-user-journeys/09-build-decisions.md`): complete, with every decision of the build and every answer Hekmat gave.

- [ ] **The index** (`README.md` of `DDP-Tracker-docs`): add rows for the screenshots folder, `RUN-THE-PROTOTYPE.md` and `prototype-summary.md`; set the dates.

- [ ] **The ledger** (`implementation-plan/progress.md`): every task done, with its commits.

- [ ] **No Project copies** (D38). The handoff asks for a Markdown copy of every document in the Claude Project under `claude/`. Hekmat dropped that rule: the folder `DDP-Tracker-docs` is connected to the Project and he only works from this computer. Save the documents here, add them to the index, and leave it at that.

---

## Task 5.5: Handover (coordinator)

- [ ] **Leave the repository clean.**

  ```bash
  git status --short                          # nothing
  git log --oneline upstream/dev..feat/user-journeys | wc -l
  ```

- [ ] **Free the branch for Hekmat.** If you worked in a worktree (your path contains `.claude\worktrees\`), the branch is checked out there, and git will not let Hekmat check it out in his clone while it is. Detach your worktree from it:

  ```bash
  git switch --detach
  ```

  The branch stays where it is; only your folder lets go of it. If you worked in the main clone, leave the branch checked out.

- [ ] **Stop what you started:** the development server, any background task.

- [ ] **The final message to Hekmat.** Short, and in this order: what is ready (the branch, how many commits, the test result); how to see it (`RUN-THE-PROTOTYPE.md`); what he has to do (push; confirm the decisions); what is open. Attach or point to four or five screenshots that show the prototype best. Say plainly what was not done or not verified.
