# Handoff: user journeys prototype for the DDP Tracker

This folder hands over a piece of work from one Claude task to another. It contains everything a new task needs to **design and build a working prototype** of a restructured DDP Tracker website with a landing page that guides eight user roles through "user journeys".

Written 30 September 2026 for Hekmat Alrouh (infrastructure track, DDP2026 Hackathon).

## Your job in one paragraph

On a new branch of Hekmat's fork of the DDP Tracker, add a landing page where visitors choose one of eight roles, and a journey page per role that walks them through 3 to 5 steps. Each step links either to a **real page that exists today** or to a **mock-up page with fictional data** for features that do not exist yet. Add a `seed_demo` management command so a fresh install has platforms, uploads, annotations and representations to show. Keep changes additive, follow the repository's conventions, write tests, check your work with screenshots, and commit (Hekmat pushes).

## Reading order

| # | File | What it gives you | Read when |
|---|---|---|---|
| 00 | `00-START-HERE.md` | This overview, where things live, working rules | First |
| 01 | `01-context.md` | The hackathon, the tool, the team, user groups, sources | Before designing |
| 02 | `02-decisions.md` | Every decision made so far, with reasons | Before designing |
| 03 | `03-site-structure.md` | Navigation, sitemap, specification of every page | While designing and building |
| 04 | `04-user-journeys.md` | The eight journeys, step by step, with target pages | While designing and building |
| 05 | `05-codebase-guide.md` | Repository map, conventions, URL names, models, how to run and test | Before writing code |
| 06 | `06-build-plan.md` | Phases, file layout, `seed_demo` spec, tests, acceptance criteria, delivery | Before and during building |
| 07 | `07-demo-data.md` | The fictional sample DDPs and what `seed_demo` should create | When building `seed_demo` |
| 08 | `08-known-issues-and-open-questions.md` | Bugs found, risks, questions still open | Before finishing |
| 09 | `09-build-decisions.md` | Empty decision log for you to fill in during the build | Throughout |

Helper files in this folder:

- `screenshot_example.py`: takes screenshots of a locally running instance (tested).
- `load_sample_ddps_example.py`: loads the sample DDPs through the real upload form (tested; the model for `seed_demo`).
- `reference-screenshots/`: the current home page and TikTok explorer, for matching the look.

Also read, outside this folder:

- `../DDP-Tracker_features-by-role.md`: the full feature analysis by role (status Exists / Partial / Gap). The journeys and mock-ups are built from it.
- `../sample-ddps/README.md`: the three fictional sample packages.

## Where things live

| What | Where |
|---|---|
| Hekmat's fork (GitHub) | https://github.com/hekmatov/ddp-tracker |
| Upstream (Nico Pfiffner) | https://github.com/Nico-AP/ddp-tracker |
| Local clone on Hekmat's computer | `C:\Users\hekma\Documents\Projects\DDP-Tracker` (remotes `origin` = fork, `upstream` = Nico's repo; branch `dev`) |
| Documents folder on Hekmat's computer | `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs` (this folder is `handoff-user-journeys` inside it) |
| Claude Project "DDP2026 Hackathon" | Text copies of all documents under `claude/`, this handoff under `claude/handoff/` |
| Live prototype of the tool | https://www.ddp-tracker.org/ (documentation at /docs/) |
| Hackathon document | https://docs.google.com/document/d/1OxUawA7hqIjOCjSmRn8rTSojv0jCSojuSXnBeLAvFRs/edit (Hekmat can paste the latest version as Markdown; the one from 30 September is summarised in `01-context.md`) |

## Working rules

1. **Writing style:** British English spelling; never use em dashes (use commas, colons, semicolons or parentheses instead). This applies to code comments, templates, commit messages and documents.
2. **Save every deliverable** (documents, screenshots, bundles) in `DDP-Tracker-docs`, and put a Markdown copy of text documents in the Project under `claude/`. Update the index in `DDP-Tracker-docs/README.md` and `claude/README.md`.
3. **Never put documents in the repository folder.** Only code goes in `DDP-Tracker`.
4. **Commit, do not push.** Claude has no GitHub credentials. Hekmat pushes from Windows.
5. **Git in the connected repository folder needs delete permission:** git creates and removes lock files. If a git command fails with "Operation not permitted" on a `.lock` file, request delete permission for the `DDP-Tracker` folder once, explaining why.
6. **Ask before big deviations** from `02-decisions.md`; small design choices are yours, but record them (see `06-build-plan.md`, "Decision log").
7. **Folder access:** this task needs both `DDP-Tracker` and `DDP-Tracker-docs` connected. If they are not, request access to both in one request.

## Definition of done

- A branch `feat/user-journeys` in the local clone with the new work committed in small, focused commits, based on the latest `upstream/dev`.
- The landing page, eight journey pages and all mock-up pages render without errors, for anonymous, signed-in and staff users.
- `seed_demo` turns an empty database into a convincing demo in one command.
- The whole test suite passes (both `pytest` and `manage.py test`), including new tests for the new pages.
- Screenshots of the landing page, at least two journeys and every mock-up page are saved to `DDP-Tracker-docs/prototype-screenshots/`.
- A short `RUN-THE-PROTOTYPE.md` in `DDP-Tracker-docs` tells Hekmat how to push the branch and run it on Windows.
- A summary of what was built, what was decided along the way, and what is left, saved to `DDP-Tracker-docs` and the Project.
