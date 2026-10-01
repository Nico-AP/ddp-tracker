# User journeys prototype: summary

Written 30 September 2026, at the end of the build, for Hekmat and the infrastructure track (DDP2026 Hackathon). How to run it: `RUN-THE-PROTOTYPE.md`. The plan it followed: `implementation-plan/`. Every decision: `handoff-user-journeys/09-build-decisions.md`.

## 1. What it is and where

A new Django app, `ddp_tracker.journeys`, on the branch **`feat/user-journeys`** of the local clone (not pushed yet). It adds:

- a landing page at `/` where a visitor picks one of eight roles;
- a journey page per role, with 4 or 5 steps that lead to pages that exist today or to mock-ups;
- twelve mock-up pages of planned features, with fictional data and a banner;
- a feature cards page in the hackathon's template;
- the management command `seed_demo`, which turns an empty database into a demo through the site's own code paths (upload, parse, approve, annotate).

The app has no models and no migrations. The previous home page is unchanged at `/overview/`.

| | |
|---|---|
| Base | `upstream/dev` at `a18b3f3` (upstream did not move during the build) |
| Commits | 28: the parser fix (`5c22c20`, see section 7), then 27 for the prototype, ending at `33d2450` |
| Tests | 197 new. `pytest`: 690 passed, none failed, coverage 97.63% (493 at the start). Django's runner: 458 tests OK (261 at the start). No existing test was changed. |
| Checks | ruff, ruff format, mypy and djlint clean; no inline style or script; no em dash |
| Changed outside the new app | `config/settings/base.py` (the app, two redirects), `config/urls.py` (one include), `ddp_tracker/core/urls.py` (the old home page moves to `overview/`), `ddp_tracker/templates/base.html` (brand link, Home, Docs, Contribute, the prototype strip), `assets/scss/main.scss` (one line), `assets/scss/pages/_journeys.scss` (new), `ddp_tracker/static/css/main.css` (rebuilt), `ddp_tracker/static/js/journeys.js` (new) |

How it was built: a coordinating task gave each of 18 implementation tasks to a fresh subagent, checked every result itself, and had the load-bearing ones reviewed by a separate reviewer. Hekmat saw screenshots and decided at three check-ins.

## 2. The pages

"Real" means the page existed before or works on real data; "mock-up" means a planned feature, shown with the banner "Prototype: this page shows fictional data to illustrate a planned feature. It does not work yet." Screenshots are in `prototype-screenshots/`.

| URL | Page | Kind | Journeys | Screenshot |
|---|---|---|---|---|
| `/` | Landing page: eight roles, how it works, live figures | Real (new) | All | `01-landing.png`, `01-landing-phone.png`, `30-landing-staff.png` |
| `/journeys/<role>/` | A journey: aim, audience, steps, features needed, other journeys | Real (new) | One each | `02-journey-*.png` (eight), `31-journey-curator-staff.png` |
| `/features/` | Feature cards in the hackathon's template | Real (new) | Linked from every journey | `22-feature-cards.png` |
| `/overview/` | The previous home page, unchanged | Real (existing) | Linked from the landing page | `23-overview.png` |
| `/prototype/concepts/` | M1 Concepts: research field, theme, platform, sort by relevance | Mock-up | Researcher | `10-concepts.png`, `10-concepts-health.png`, `10-concepts-phone.png` |
| `/prototype/concepts/<slug>/` | M2 Concept detail: per platform paths, types, formats, whose time, examples, no-data markers, translations | Mock-up | Researcher | `11-concept-watched-video.png` (and `-phone`) |
| `/prototype/shortlist/` | M3 Study shortlist: notes, share link, codebook (CSV), DDM File Blueprints (JSON), ethics summary | Mock-up | Researcher, engineer | `12-shortlist.png` (and `-phone`) |
| `/prototype/compare/` | M4 Compare platforms: concept matrix, how people get their data, documentation gap | Mock-up | Policy | `13-compare.png` (and `-phone`) |
| `/prototype/platforms/<slug>/changes/` | M5 Changelog per platform | Mock-up | Engineer, policy | `14-changes-tiktok.png` |
| `/prototype/api/` | M6 API: endpoints (with explainers for donation tools), exports, `llms.txt`, MCP tools, licence | Mock-up | Engineer, machine consumer | `15-api.png` |
| `/prototype/snapshots/` | M7 Snapshots: releases, DOI, citation to copy, pinning | Mock-up | Policy, machine consumer | `16-snapshots.png` |
| `/prototype/request/<slug>/` | M8 Request your data: steps per platform, the paired-export hint | Mock-up | Contributor | `17-request-tiktok.png` |
| `/prototype/moderate/` | M9 Moderator dashboard: queues per platform, "Annotate next", community questions, contributors | Mock-up | Curator | `18-moderate.png` (and `-phone`), `32-moderate-staff.png` |
| `/prototype/moderate/seed/` | M10 Seed annotations: official documentation, paired uploads, AI suggestions | Mock-up | Curator | `19-seed-documentation.png`, `19-seed-pairs.png`, `19-seed-ai.png` |
| `/prototype/admin/roles/` | M11 Roles and platforms: roles, people, hubs, platforms, path rules | Mock-up | Administrator | `20-roles.png` |
| `/prototype/learn/<slug>/` | M12 What a platform keeps about you: plain categories, one example, an exercise | Mock-up | Learner | `21-learn-tiktok.png` (and `-phone`) |

Existing pages the journeys use, as they are: the explorer (`24-explorer-tiktok.png`), approvals (`33-approvals-staff.png`), the suggestion queue (`34-suggestions-staff.png`), the review of the September TikTok upload (`35-review-tiktok-staff.png`), the inspection of the held YouTube upload as its uploader (`40-inspect-held-youtube-curator.png`), and the annotation, representation, vocabulary, upload, docs and health pages.

Navigation (D21): the header keeps the pages that exist (Home, Explore, Docs, Contribute or the account items); a strip below it, "Prototype previews", holds Concepts, Compare, API, and Curate for staff.

## 3. What is real in the mock-ups, and what is fictional

`seed_demo` creates, through the real upload and curation code: 2 demo users, 4 platforms, 5 uploads (TikTok March and September 2026, Instagram, Facebook, and a held YouTube upload), 28 annotations, 9 representations, 21 example values, 1 open suggestion and 1 suggested vocabulary term ("liked"). The packages themselves are generated in memory from a fixed seed; nothing binary or personal is in git.

| Page | From the demo database | Fictional (fixed in the page's module) |
|---|---|---|
| M1, M2 Concepts | Which platforms provide a concept, its paths, types, formats, first and last seen, number of uploads, personal-data flag, annotations, curated example values | The concepts' wording, research fields and themes, "on N studies' shortlists", official documentation texts, "whose time" notes, no-data markers, translations |
| M3 Shortlist | Every row (paths, types, formats, personal data), the ethics count, both exports | Nothing; the shortlist lives in the visitor's session |
| M4 Compare | The concept matrix, the figures per platform | How people get their data, the documentation gap counts |
| M5 Changelog | Everything: added, moved, changed and removed, computed from observations (TikTok: 5, 33, 1, 1) | Nothing |
| M6 API | Nothing (the API does not exist) | Every request and answer, `llms.txt`, the MCP tools |
| M7 Snapshots | Nothing | Releases, figures, DOIs (prefix `10.0000/fictional`, which resolves to nothing) |
| M8 Request | The platform's id for the upload form | The instructions |
| M9 Dashboard | Every queue (TikTok: 177 of 190 data points to triage, 1 annotation suggestion, 17 lists without a representation), "Annotate next" | Which platforms "you" moderate, the questions, the top contributors |
| M10 Seeding | Nothing | Everything, the official texts included |
| M11 Roles | Platforms and their figures, path rules | People, roles, hubs, working groups |
| M12 Learn | The counts per category, the example annotation and its curated values | The categories' wording, the exercise |

At Hekmat's request (Phase 3 check-in), nothing on a page is tagged "fictional": the banner says it once per page. The downloaded codebook and blueprints still say "fictional demo data", because files travel without the banner.

## 4. What came from the hackathon notes

From the latest hackathon document, section Infrastructure Track, and where it was built.

| Note | What was built | Where |
|---|---|---|
| Core questions for a journey: aim, how to reach it, how the interface looks, which features are needed | Every journey page: Aim, Who this is for, Steps (each to a page), Features this journey needs (Exists, Partial, Gap) | Journey pages |
| "Today: focus on researcher roles together" | The researcher builds a shortlist and shares a link; the engineer's journey opens it | M3, journeys 1 and 2 |
| Datetime standards; whose time zone a timestamp shows (`tz_whos`) | "Whose time?" per platform; a `tz_whos` column in the codebook; a feature card | M2, M3, feature cards |
| Field-specific top-level ontology | Research field selector (communication science, public health, economics) with its own themes | M1 |
| Default public page versus community page; explore "without annotation mask" | The landing page is public; the concept view links to the full structure in the explorer | Landing page, M1 |
| API endpoints for researchers and LLMs | Endpoint list, `llms.txt`, MCP tools | M6 |
| Annotations as explainers for participants, as an API endpoint | An explainers endpoint; the learner's page says donation tools could show them | M6, M12 |
| Sort data point lists by most used or relevant | Sort concepts by relevance ("on N studies' shortlists") | M1 |
| Prioritise annotations that are actually important | "Annotate next", ordered by how many uploads contain the data point | M9 |
| Seed annotations from platform documentation; official documentation as its own kind | Official documentation tab, "Official" as its own kind next to the curator's annotation | M10, M2 |
| Gaps between platform documentation and actual DDPs | "Documented but not observed" and "observed but not documented", and a count per platform | M10, M4 |
| Pairing of HTML and JSON; paired donation sets | Paired uploads tab; a hint on the request page to request the same export twice; a feature card | M10, M8, feature cards |
| AI-flagged labels, checked with time | AI suggestions tab, each to accept or reject | M10 |
| Referencable archive | Monthly snapshots with a DOI and a citation to copy | M7 |
| Crowdsource annotation work and questions | "Questions from the community", "Top contributors this month" | M9 |
| Extra information or comment field for annotations | "Sources and notes" (the annotation's note) | M2 |
| Governance: DDP hubs per platform, working groups | "Your platforms" on the dashboard; a hubs table with working groups | M9, M11 |
| Translations for fields, as a dictionary | "This concept in other languages" | M2 |
| Example values as a table with title and value | Examples table | M2, M12 |
| No PII published (DPIA, ethical review) | Ethics summary on the shortlist: how many chosen data points are personal data | M3 |
| "No data" markers | "No data markers" line (TikTok comments use `N/A`); a feature card | M2, feature cards |
| Data logs as data donations | Not designed | Open question (section 8) |

## 5. Decisions to confirm

Confirmed by Hekmat during the build: **D20** (the previous home page moves to `/overview/`), **D21** (prototype pages in their own strip, not in the main navigation), D37 (the parser fix on the branch), D38 (documents here only), and **no "fictional" tags on pages**.

Still to confirm (made by the planning task; each with its reason in the decision log):

| # | In short |
|---|---|
| D19 | Built in the local clone; no bundle; Hekmat pushes |
| D22 | File layout: `journeys/demo/` for demo data, `journeys/mockups/` one module per page |
| D23 | A journey page answers the hackathon's four core questions |
| D24 | A step can have a "today" link and a "demo" link into the seeded data |
| D25 | Likes use the existing term `responded`; the demo curator suggests "liked", which stays unapproved |
| D26 | A second, non-staff demo user with a held upload, a suggestion and a suggested term |
| D27 | The March TikTok package differs from September in four planned ways |
| D28 | Paired donation sets have no page of their own; they are a tab of M10 |
| D29 | The API mock-up has an explainers endpoint for donation tools |
| D30 | A feature cards page in the hackathon's template |
| D31 | The compiled `main.css` is committed with every Sass change |
| D32 | The pre-commit hooks were run by hand; the git hook is not installed |
| D33 | Real seeded data where it exists; otherwise a note to run `seed_demo` |
| D34 | No language filter on the concept view (the demo data is English only) |
| D35 | Demo password: changed after delivery. It is never in the code: `seed_demo` reads `DJANGO_DEMO_PASSWORD`, or makes up a random one and prints it (GitGuardian flagged the fixed one on the pull request) |
| D36 | A shared shortlist is a link with the concepts in the query string |

Decisions made during the build (all in the decision log), the ones worth a look:

- The moderator dashboard shows how many uploads wait for approval **to staff only**, as the real site does (the plan had shown it to everyone).
- The prototype's green and amber labels use darker text than the site's own badges, to meet WCAG AA contrast; the site's badges were left as they are.
- Copy buttons are ordinary Bootstrap buttons with a status line that screen readers announce, because the reviews app already uses the class name `copy-button` for something else.
- The shortlist's two export previews are folded away; the shared shortlist's button says "Add these to my shortlist"; the CSV opens correctly in Excel on Windows.
- Breadcrumbs read "Home / Journeys / <role>" and "Home / Prototype previews / <page>".

## 6. What is left, and the rough edges

Nothing in the plan was dropped: every page exists with content, every journey step leads where it says (walked signed out, as the demo admin and as the demo curator).

Rough edges and limits, honestly:

- **The explorer scrolls sideways on a phone** (`/platforms/<slug>/`, about 519 pixels wide at 375). It did so before this work (its filter control and tree rows); the prototype did not change it.
- **Demo links find the demo uploads by platform and state,** not by who uploaded them. On a database with real uploads, "Open the review of the demo TikTok upload" could open a real one. Fine for a demo database.
- **The changelog** compares an upload with the latest earlier one only. Two packages with the same request date would give two entries, and packages from different people can differ without the platform changing. It shows the idea, not a finished method.
- **The dashboard's figures** count every counted upload, while the explorer by default shows only the most common request format, so they could differ for a platform with uploads in several formats (not the case in the demo).
- **The DDM File Blueprints** export is illustrative. It lists what a blueprint needs (file, format, where the list sits, required fields, fields to keep, personal data) but is not the Data Donation Module's import format.
- **The concept view** makes about 228 database queries per page. That is acceptable for a mock-up, but not for the real feature.
- **Not tried:** the Docker route, PostgreSQL (CI runs the suite there), and a real screen reader (the accessibility checks are automated: headings, labels, header cells, named links and buttons, breadcrumbs, and phone width in Edge).
- **The screenshot tool** assumes the upload numbers of a fresh `seed_demo` database (the September TikTok upload is 2, the held YouTube upload is 5).

## 7. Findings on the way, worth reporting to Nico

1. **Two parser tests fail on Windows.** The Windows registry maps `.csv` to `application/vnd.ms-excel`, and `detect_mime` asked the machine's own table. A fix (one commit, with a test) sits on the branch `fix/parser-mime-registry` and is also the first commit of the prototype branch (D37). It can be offered as its own pull request.
2. **`npm run build` fails on Windows:** `build:vendor` uses `mkdir -p` and `cp`. `npm run build:css` works; the vendor files are committed anyway.
3. **`AGENTS.md` says `main.css` is not committed**, but upstream commits it with every Sass change (the build did the same, D31).
4. **A template trap:** `base.html` sets `waiting` (the number of approvals) for staff, which silently overwrites a page's own context variable of that name. It cost one crash during the build.
5. The findings of the handoff still stand (`handoff-user-journeys/08-known-issues-and-open-questions.md`): the possible TikTok username leaks in paths (K1, K2), Facebook `_v2` keys collapsed to `{*}` (K3), the registration e-mail's example.com (K4), and the others.

## 8. Open questions for the track

1. Offer the prototype to Nico as a pull request, or keep it as a fork prototype for the hackathon? (If it is offered before the parser fix is merged, it carries that commit too.)
2. Is a "researcher" a distinct account type, or is the concept view simply public?
3. Final navigation labels ("Concepts", "Compare", "Curate") once features are real.
4. Who may become a platform moderator, and who appoints them (hubs, working groups)?
5. Which export targets matter most: DDM, Port, plain JSON Schema?
6. What licence should the curated schema knowledge carry (the snapshots and the API assume one)?
7. May AI-suggested labels be public before a person has checked them?
8. Data logs as data donations: not designed yet.
