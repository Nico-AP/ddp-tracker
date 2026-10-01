# 02. Decisions so far

All decisions were made by Hekmat on 30 September 2026 unless marked otherwise. "Proposed" means Claude proposed it and Hekmat asked for this handoff to be written based on it; treat proposed items as the plan, but they can still be refined during design if there is a good reason (record it).

## Repository and workflow

| # | Decision | Reason |
|---|---|---|
| D1 | Work on Hekmat's fork `hekmatov/ddp-tracker`, cloned from `dev` (upstream's default and integration branch). `main` is almost empty and `stage` equals `dev`. | `dev` is where all work happens (upstream CONTRIBUTING.md). |
| D2 | Upstream is added as remote `upstream`. Keep `dev` in sync with `upstream/dev`; do new work on a feature branch. | Allows offering changes back to Nico as pull requests. |
| D3 | Branch name: `feat/user-journeys` (proposed). | Follows upstream's `feat/…` convention. |
| D4 | Claude commits; Hekmat pushes. | No GitHub credentials in Claude's environment. |
| D5 | Documents live in `DDP-Tracker-docs` next to the repository, with Markdown copies in the Project under `claude/`. Never in the repository. | One place for all outputs, visible to every task; keeps the repository clean. |

## The prototype

| # | Decision | Reason |
|---|---|---|
| D6 | Build a **working version in the fork** (real Django pages), not a standalone mock-up. | Hekmat's choice. |
| D7 | Journeys cover **all eight roles**. | Hekmat's choice. |
| D8 | Steps that need features that do not exist yet are **mocked up**: real pages in the app showing what the feature could look like, with fictional data and a clear "Prototype" label. | Hekmat's choice; makes the feature list tangible. |
| D9 | Claude **proposes the site structure** (done: see `03-site-structure.md`). | Hekmat's choice. |
| D10 | Changes are **additive**: a new Django app (`journeys`, proposed) holds the landing page, journey pages and mock-ups. Existing apps are only touched where necessary (home page route, navigation). | Upstream changes daily (72 commits between 11 and 30 September); additive work conflicts least and is easier to offer back. |
| D11 | The home page `/` becomes the role picker (proposed). The previous home page content is not lost: its Explore / Contribute / Curate cards can move into the landing page or a secondary section. | The landing page is the point of the prototype. |
| D12 | Mock-up pages live under `/prototype/…` and carry a visible banner "Prototype: fictional data, not a working feature" (proposed). | Nobody should mistake them for real features or real data. |
| D13 | Each journey step shows a status badge: **Available** (links to a real page) or **Prototype** (links to a mock-up) (proposed). Some steps are partly available; use Available when the linked page does the job today, and say what is missing in the step text. | Makes the roadmap visible. |
| D14 | Add a `seed_demo` management command that loads the fictional sample DDPs plus fictional annotations and representations (proposed). | A fresh install is empty; journeys need content. |
| D15 | Follow upstream conventions exactly (see `05-codebase-guide.md`): uv only, Bootstrap 5 via Sass, htmx, no inline scripts or styles (CSP), no JS bundler, `django.test.TestCase` tests. | Needed for the work to be mergeable and for production CSP. |

## Earlier decisions that shape the content

| # | Decision | Where |
|---|---|---|
| D16 | Eight roles, as defined in the features analysis. | `../DDP-Tracker_features-by-role.md`, section 2 |
| D17 | "Two views, one model, and a hand-off" as the answer to the exhaustive-versus-digestible tension. | Features analysis, section 5 |
| D18 | The sample DDPs are fictional (persona "Noor Vermeulen") and structurally modelled on the live tracker. | `../sample-ddps/README.md` |

## Not yet decided

See `08-known-issues-and-open-questions.md`. In short:

- whether to offer the work back to Nico as a pull request;
- whether a researcher is a distinct account type;
- the final name and placement of navigation items.
