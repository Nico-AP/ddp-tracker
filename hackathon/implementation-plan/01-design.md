# 01. Design

Read this before any task. It fixes the names, interfaces and rules that the tasks share. The background is in `../handoff-user-journeys/` (decisions D1 to D18 in `02-decisions.md`, pages in `03-site-structure.md`, journeys in `04-user-journeys.md`).

## 1. What is being built

A new Django app, `ddp_tracker.journeys`, on the branch `feat/user-journeys`:

- a **landing page** at `/` where a visitor picks one of eight roles;
- a **journey page** per role (`/journeys/<role>/`) with 3 to 5 steps, each leading to a page that exists today or to a mock-up;
- **twelve mock-up pages** under `/prototype/…` that show planned features with fictional data and a banner;
- a **feature cards page** (`/features/`) that presents the planned features in the hackathon's feature template;
- a management command, **`seed_demo`**, that turns an empty database into a demo;
- tests for all of it.

The app has **no models and no migrations**. Everything it stores is either in the session (the study shortlist) or created by `seed_demo` as ordinary rows of the existing apps.

## 2. Decisions added by this plan

They continue the numbering of `../handoff-user-journeys/02-decisions.md`. The coordinator copies them into `../handoff-user-journeys/09-build-decisions.md` in Phase 0 (date 30 September 2026, decided by "planning task, to be confirmed by Hekmat").

| # | Decision | Reason |
|---|---|---|
| D19 | Build in Claude Code on Hekmat's Windows computer, in the local clone (a git worktree of it). No cloud container and **no git bundle**: the branch `feat/user-journeys` is created in the clone itself and Hekmat pushes it. | The task now has direct access to the repository. |
| D20 | `/` is served by the `journeys` app. The previous home page stays, unchanged, at `/overview/` and keeps its URL name `core:index`. After logging in or out, users land on `/`. | The previous page's tests keep passing unchanged, and its content is not lost (D11). |
| D21 | Navigation: the main row holds only pages that exist (Home, Explore, Docs, the account items). Prototype pages sit in a separate strip below it, labelled "Prototype previews" (Concepts, Compare, API, and Curate for staff). | Nobody should mistake a mock-up for a feature (D12), and it answers open question 3 without cluttering the main row. It differs from the single row in `03-site-structure.md`. |
| D22 | File layout: `journeys/demo/` holds the demo data (builders, specification, seeding) and `journeys/mockups/` holds one module per mock-up page (its fictional data and its view). | Each later task touches only its own files. The handoff proposed single `views.py` and `prototype_data.py` files. |
| D23 | A journey page follows the hackathon's core questions for a journey: the **aim**, **how to reach it** (the steps), **what the interface looks like** (each step's page) and **which features it needs** (a table with the status Exists, Partial or Gap). | The hackathon document asks for exactly this under "How do the most likely user journeys look like". |
| D24 | A step can carry two extra links: a "today" link (the closest page that exists, for a prototype step) and a "demo" link into the seeded data (for example the review of the demo TikTok upload), shown only when the data exists and the user may open it. | Steps whose target needs a primary key (an upload, an annotation) cannot be fixed URLs. |
| D25 | Likes and reactions use the existing activity term `responded`. The demo curator also suggests a new term "liked", which stays unapproved. | The vocabulary has no "liked". An unapproved term must not appear in public representations, and the pending term gives the administrator's journey something to approve. |
| D26 | `seed_demo` also creates a second, non-staff user (`demo-curator@example.org`) with a held YouTube upload, one open suggestion and the suggested term. | The approvals queue, the suggestion queue and the "inspect a held upload" step then have something to show. |
| D27 | The extra TikTok package (requested 15 March 2026) differs from the September one in four ways: the section `Your Activity` is called `Activity` and its `Watch History` is called `Video Browsing History`; there is no `Tiktok Live` section; the dates in the like list are ISO 8601 with a `Z`; the profile has a field `likesReceived` that September lacks. | Verified: September then shows moved, new, changed and missing data points. |
| D28 | The mock-up "Seed annotations" (M10) shows three sources as tabs: official documentation, paired uploads, and AI-suggested labels. Paired donation sets therefore have no page of their own. | The hackathon notes list these sources together under "Seeding Annotations", and the journeys stay at 5 steps. |
| D29 | The API mock-up (M6) includes an endpoint for participant-facing explainers, for donation tools such as the DDM. | Hackathon note: "annotations as explainers for participants, as api endpoint for researchers?" |
| D30 | A feature cards page renders the planned features in the hackathon's template (title, problem, solution, user group, technical implementation), each linking to the mock-up that illustrates it. | It lets the track paste or compare cards directly. |
| D31 | Sass changes are compiled with `npm run build:css` and the compiled `ddp_tracker/static/css/main.css` is committed with them. | That is what upstream does in every Sass commit, whatever `AGENTS.md` says. |
| D32 | The pre-commit hooks are run by hand (`uv run pre-commit run` on the staged files) before every commit. The git hook is **not** installed. | Installing it would tie Hekmat's clone to a virtual environment inside a temporary worktree. |
| D33 | A mock-up shows real seeded data where it can. Where the database has none, it shows a short note ("Run `seed_demo` to see this with data") instead of a second, made-up copy of that data. | Keeps the fictional modules small and the pages honest. |
| D34 | The concept view has no language filter; it says that the demo data is English only. | One language in the demo data makes a filter meaningless. |
| D35 | Demo passwords: a fixed, documented password when `DEBUG` is on; a random one, printed once, when `--force` is used without `DEBUG`. | A known superuser password must never reach a real deployment. |
| D36 | A shared shortlist is a link with the chosen concepts in the query string (`?c=watched-video&c=searched`). | The session shortlist belongs to one browser; the hand-off to an engineer needs a link that works elsewhere. |
| D37 | The prototype branch starts with one commit that is not the prototype's: the parser fix from the branch `fix/parser-mime-registry` (the MIME type of a file no longer depends on the machine's own table). The fix also stays on its own branch, to offer to Nico by itself. Decided by Hekmat on 30 September 2026. | Without it two parser tests fail on Windows, and Hekmat wants the build's test runs to be green. The price: if the prototype branch is offered upstream before the fix is merged, it carries that parser commit too. |
| D38 | Documents are saved in `DDP-Tracker-docs` only. The handoff's rule to also put a Markdown copy of each in the Claude Project under `claude/` no longer applies. Decided by Hekmat on 30 September 2026. | The folder is connected to the Project and Hekmat only works from this computer, so every task can read the documents where they are. |

## 3. What the hackathon notes add

From the latest hackathon document, section Infrastructure Track. "Where" names the page that shows it.

| Note in the hackathon document | Design feature | Where |
|---|---|---|
| Core questions: define an aim, how to reach it, how the interface looks, which features are needed | Journey page structure (D23); feature table per role | Journey pages |
| "Today: focus on researcher roles together" | The researcher and engineer journeys share the shortlist: one builds it, the other opens it | M3, journeys 1 and 2 |
| Different datetime standards; whose time zone a timestamp shows; feature card "Timezone specification" (`tz_whos`, TikTok looks like UTC) | A "Whose time?" line per platform on the concept detail, and a `tz_whos` column in the codebook export | M2, M3 |
| Field-specific top-level ontology | A research field selector (communication science, public health, economics), each with its own themes that map onto the same concepts | M1 |
| Default public page versus community page; explore view "without annotation mask" | The landing page is the public default; the concept view links to "the full structure" (the explorer) | Landing page, M1 |
| API endpoints for researchers and LLMs | Endpoint list, `llms.txt`, MCP tools | M6 |
| Annotations as explainers for participants, as API endpoint | Explainers endpoint (D29); the learner page says the same explainers can be shown by donation tools | M6, M12 |
| Sort data point lists by most used or relevant | Sort concepts by "used in N studies" | M1 |
| Prioritise annotations that are actually important | An "Annotate next" list on the moderator dashboard, ordered by how many uploads contain the data point | M9 |
| Integrate platform documentation to seed annotations; a separate annotation kind for official documentation; example: Facebook variable descriptions by Meta | Official documentation tab, with "official" marked as its own kind next to the curator's annotation | M10, M2 |
| Gaps between platform documentation and actual DDPs | "Documented but not observed" and "observed but not documented" rows, and a count per platform in the comparison | M10, M4 |
| Pairing of HTML and JSON; feature card "Paired donation sets" | Paired uploads tab; a hint on the request instructions to request the same export twice | M10, M8 |
| Major work at the beginning: how to seed (AI-flagged labels, checked with time) | AI-suggested labels tab, each marked "needs a human check" | M10 |
| Referencable archive | Monthly snapshots with a (fictional) DOI and a citation | M7 |
| Crowdsource annotation work; incentive to add new DDPs; crowd source annotation questions | "Questions from the community" and "Top contributors" cards | M9 |
| Extra information or comment field, documentation for annotation | "Sources and notes" on the concept detail (the annotation's note) | M2 |
| Governance: DDP hubs per platform that assign moderators; working groups per platform | "Your platforms" on the dashboard; a hubs table with moderators and a working group | M9, M11 |
| People add translations for fields, to build a dictionary | "Field names in other languages" table with an "Add a translation" button | M2 |
| Show example values as a table with title and value; annotate specific labels | Examples table on the concept detail | M2 |
| How is ensured that no PII is published (DPIA, ethical review) | An "Ethics summary" on the shortlist: how many chosen variables are flagged as personal data | M3 |
| "No data" markers (second group) | A "No data markers" line on the concept detail; the demo data contains a real one (`N/A` in TikTok comments) | M2 |
| Data logs as data donations (open) | Not designed. Listed as an open question in the summary. | None |

## 4. Architecture

### 4.1 New files

```
ddp_tracker/journeys/
  __init__.py
  apps.py                      JourneysConfig
  content.py                   the eight roles: aim, audience, steps, features (data)
  targets.py                   demo links from steps into the seeded data
  feature_cards.py             the hackathon feature cards (data)
  views.py                     index, journey, features
  urls.py                      every route of the app, including the mock-ups
  demo/
    __init__.py
    ddps.py                    fictional DDPs, built in memory (no binary files in git)
    spec.py                    what seed_demo creates (users, platforms, uploads, annotations …)
    seed.py                    seed() and reset()
  management/__init__.py
  management/commands/__init__.py
  management/commands/seed_demo.py
  mockups/
    __init__.py                MOCKUPS (the registry), render_mockup(), find_platform()
    concepts.py                M1 and M2: fields, themes, concepts, and their real data
    shortlist.py               M3: the session shortlist and its exports
    compare.py                 M4
    changes.py                 M5
    api.py                     M6
    snapshots.py               M7
    instructions.py            M8
    moderate.py                M9
    seeding.py                 M10
    roles.py                   M11
    learn.py                   M12
  templates/journeys/
    index.html  journey.html  features.html
    _step.html  _prototype_banner.html  _prototype_nav.html
    prototype/base.html  prototype/placeholder.html
    prototype/concepts.html  concept.html  shortlist.html  compare.html  changes.html  api.html
    prototype/snapshots.html  request.html  moderate.html  seed.html  roles.html  learn.html
  tests/
    __init__.py
    utils.py                   SeededTestCase
    test_demo_ddps.py  test_seed_demo.py
    test_content.py  test_views.py  test_mockups.py  test_conventions.py
    test_concepts.py  test_shortlist.py  test_changes.py  test_api.py
    test_compare.py  test_snapshots.py  test_instructions.py  test_moderate.py
    test_seeding.py  test_roles.py  test_learn.py  test_feature_cards.py
    test_accessibility.py
assets/scss/pages/_journeys.scss
ddp_tracker/static/js/journeys.js          copy-to-clipboard buttons only
```

### 4.2 Existing files that change (and nothing else)

| File | Change | Task |
|---|---|---|
| `config/settings/base.py` | Add `"ddp_tracker.journeys"` to `LOCAL_APPS` (task 1.1). Set `LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL` to `"journeys:index"` (task 2.1). | 1.1, 2.1 |
| `config/urls.py` | Include `ddp_tracker.journeys.urls` before `ddp_tracker.core.urls`. | 2.1 |
| `ddp_tracker/core/urls.py` | The index route moves from `""` to `"overview/"`; its name stays `index`. | 2.1 |
| `ddp_tracker/templates/base.html` | Brand link, three navigation links, one include. | 2.2 |
| `assets/scss/main.scss` | One `@use` line. | 2.2 |
| `ddp_tracker/static/css/main.css` | Rebuilt (D31). | 2.2 and any task that changes Sass |

One more change is on the branch but is not part of any task: the parser fix (D37), picked in Phase 0 as the branch's first commit. It touches `packages/ddp-parser/src/ddp_parser/source/mime.py` and adds one test to `packages/ddp-parser/tests/test_source.py`.

`ddp_tracker/core/tests/tests.py` and every other existing test must pass **unchanged**. If an existing test has to change, stop and tell the coordinator.

### 4.3 Rules every file follows

- **Additive.** Do not refactor existing apps. Use their public functions (listed in 5.6).
- **No inline styles, no inline scripts, no `style="…"`, no `<script>` without `src`, no external fonts or CDNs.** The production content security policy forbids them, and local development does not enforce it, so a test does (`test_conventions.py`).
- **Bootstrap first.** Buttons always name a variant and, if not the default, a size: `btn btn-primary`, `btn btn-secondary btn-sm`. For a secondary action use `btn-secondary` (a light grey fill with dark text): `btn-outline-secondary` is too pale on white to read well (seen in the planning screenshots). Tables are plain Bootstrap (`table`, `table-sm`), with `text-break` on cells that hold paths. No Bootstrap `.modal`.
- **Privacy.** Never show an e-mail address of a user. Accounts appear as `#<id>`. Never store or show raw DDP values other than the curated, fictional example values.
- **Fictional means obviously fictional.** No real people, no real account handles, no data from the live site. E-mail addresses use `example.org`, DOIs use the prefix `10.0000/fictional`.
- **Writing.** British English (colour, behaviour, licence as a noun, recognise). Never an em dash: use a comma, colon, semicolon or parentheses. This covers templates, comments, docstrings, test names, commit messages and documents. Plain words: the audience includes students and policy people.
- **Typing and linting.** Annotate every function signature. Ruff's rule set is strict: fix what it reports; a `# noqa` needs the rule code and a reason on the same line.

## 5. Shared interfaces

Tasks rely on these names exactly. A task that needs to change one tells the coordinator first.

### 5.1 URLs (`ddp_tracker/journeys/urls.py`, `app_name = "journeys"`)

| Name | Path | View | Methods |
|---|---|---|---|
| `journeys:index` | `` | `views.index` | GET |
| `journeys:journey` | `journeys/<slug:role>/` | `views.journey` | GET |
| `journeys:features` | `features/` | `views.features` | GET |
| `journeys:concepts` | `prototype/concepts/` | `mockups.concepts.concept_list` | GET |
| `journeys:concept` | `prototype/concepts/<slug:slug>/` | `mockups.concepts.concept_detail` | GET |
| `journeys:shortlist` | `prototype/shortlist/` | `mockups.shortlist.shortlist` | GET |
| `journeys:shortlist-add` | `prototype/shortlist/add/` | `mockups.shortlist.add` | POST |
| `journeys:shortlist-remove` | `prototype/shortlist/remove/` | `mockups.shortlist.remove` | POST |
| `journeys:shortlist-clear` | `prototype/shortlist/clear/` | `mockups.shortlist.clear` | POST |
| `journeys:shortlist-codebook` | `prototype/shortlist/codebook.csv` | `mockups.shortlist.codebook` | GET |
| `journeys:shortlist-blueprint` | `prototype/shortlist/blueprint.json` | `mockups.shortlist.blueprint` | GET |
| `journeys:compare` | `prototype/compare/` | `mockups.compare.compare` | GET |
| `journeys:changes` | `prototype/platforms/<slug:slug>/changes/` | `mockups.changes.changes` | GET |
| `journeys:api` | `prototype/api/` | `mockups.api.api_overview` | GET |
| `journeys:snapshots` | `prototype/snapshots/` | `mockups.snapshots.snapshots` | GET |
| `journeys:request` | `prototype/request/<slug:slug>/` | `mockups.instructions.request_instructions` | GET |
| `journeys:moderate` | `prototype/moderate/` | `mockups.moderate.dashboard` | GET |
| `journeys:seed` | `prototype/moderate/seed/` | `mockups.seeding.seed_sources` | GET, POST |
| `journeys:roles` | `prototype/admin/roles/` | `mockups.roles.roles` | GET, POST |
| `journeys:learn` | `prototype/learn/<slug:slug>/` | `mockups.learn.learn` | GET |

All pages are public. The mock-ups of staff features (M9, M10, M11) are illustrations, so anyone may look at them.

### 5.2 `content.py`

```python
AVAILABLE, PROTOTYPE = "available", "prototype"  # a step's status
ANYONE, ACCOUNT, STAFF = "anyone", "account", "staff"  # who can use a step's page today
EXISTS, PARTIAL, GAP = "exists", "partial", "gap"  # a feature's status


@dataclass(frozen=True)
class Step:
    title: str
    text: str
    link_label: str
    url_name: str
    url_args: tuple[str, ...] = ()
    query: str = ""
    fragment: str = ""
    status: str = AVAILABLE
    needs: str = ANYONE
    missing: str = ""
    today_label: str = ""
    today_url_name: str = ""
    today_url_args: tuple[str, ...] = ()
    demo_link: str = ""  # a key of targets.DEMO_LINK_KEYS
    # properties: url, today_url, needs_label


@dataclass(frozen=True)
class Feature:
    title: str
    status: str
    hackathon: bool = False
    note: str = ""
    # property: status_label


@dataclass(frozen=True)
class Role:
    slug: str
    name: str
    card_line: str  # completes "I want to …"
    aim: str
    audience: str
    steps: tuple[Step, ...]
    features: tuple[Feature, ...]
    # properties: available_count, prototype_count


ROLES: tuple[Role, ...]  # eight, in the order of the landing page
ROLES_BY_SLUG: dict[str, Role]
```

Role slugs: `researcher`, `engineer`, `policy`, `contributor`, `curator`, `admin`, `machine`, `learner`.

### 5.3 `targets.py`

```python
@dataclass(frozen=True)
class DemoLink:
    label: str
    url: str

DEMO_LINK_KEYS: tuple[str, ...]   # ("tiktok-review", "held-upload", "watched-video")
def demo_link(key: str, user: AbstractBaseUser | AnonymousUser) -> DemoLink | None
```

### 5.4 `mockups/__init__.py`

```python
DEMO_PLATFORMS: dict[str, str]    # {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube"}

@dataclass(frozen=True)
class Mockup:
    key: str                      # "concepts"
    number: str                   # "M1"
    title: str
    lead: str
    url_names: tuple[str, ...]    # the URL names that belong to this mock-up
    feature: str                  # the planned feature, in words
    section: str                  # section of the features analysis, e.g. "4.1"
    hackathon: str = ""           # the hackathon note it illustrates, if any

MOCKUPS: dict[str, Mockup]        # keys: concepts, concept, shortlist, compare, changes, api,
                                  #       snapshots, request, moderate, seed, roles, learn
def roles_using(mockup: Mockup) -> list[Role]
def render_mockup(request: HttpRequest, key: str, template: str, context: dict[str, Any] | None = None) -> HttpResponse
def find_platform(slug: str) -> tuple[str, Platform | None]   # name, and the platform if this database has it; Http404 for an unknown slug
```

Every mock-up template extends `journeys/prototype/base.html` and fills `{% block mockup %}` (and `{% block heading %}` where the `h1` should differ from the mock-up's title, for example "TikTok: changelog"). The base template shows the banner, a breadcrumb, the title (`h1`), the lead, the block, and a footer "Where this fits" (the journeys that use the page, the planned feature, the hackathon note).

The banner text is fixed: **"Prototype: this page shows fictional data to illustrate a planned feature. It does not work yet."**

### 5.5 `demo/`

```python
# demo/ddps.py
SEPTEMBER: datetime               # 2026-09-15 10:30 UTC
MARCH: datetime                   # 2026-03-15 10:30 UTC
TIKTOK_FILE = "user_data_tiktok.json"
type Files = dict[str, Any]       # zip member name → bytes (as is), str (UTF-8 text) or anything JSON can write
def tiktok(request_date: datetime = SEPTEMBER) -> Files
def tiktok_march() -> Files
def instagram() -> Files
def facebook() -> Files
def youtube() -> Files
def build_zip(files: Files) -> bytes          # the same bytes on every call

# demo/spec.py
ADMIN_EMAIL = "demo-admin@example.org"
CURATOR_EMAIL = "demo-curator@example.org"
DEMO_PASSWORD = "<removed>"  # since 1 October 2026 read from DJANGO_DEMO_PASSWORD, never in the code
PLATFORMS: tuple[tuple[str, str], ...]        # (slug, name)
UPLOADS: tuple[UploadSpec, ...]
ANNOTATIONS: tuple[AnnotationSpec, ...]
REPRESENTATIONS: tuple[RepresentationSpec, ...]
EXAMPLES: tuple[ExampleSpec, ...]

# demo/seed.py
def seed(password: str) -> Counter[str]       # what was created, by kind; creates nothing twice
def reset() -> Counter[str]                   # what was deleted, by kind
```

Command: `uv run manage.py seed_demo [--reset] [--force]`.

### 5.6 Functions of the existing apps that the new code may call

| Need | Use |
|---|---|
| Parse an upload through the real code path | `ddp_tracker.ddps.tasks.parse_upload.call(upload_id, path)` (runs now, whatever the task backend) |
| Approve, confirm | `ddp_tracker.ddps.checks.approve(upload, user)`, `checks.confirm(upload, user)` |
| Anonymise a file name | `ddp_tracker.ddps.names.anonymize_file_name(name)` |
| Create an annotation on a location, link another location to it | `ddp_tracker.schemas.services.create_annotation(location, name, user, description=, note=, pii=)`, `services.link(location, annotation)` |
| Add example values | `ddp_tracker.schemas.examples.add_examples(location, values, USER_INPUT)` |
| Link a metadata data point to a representation | `ddp_tracker.representations.services.describe(representation, location, role, subject)` |
| Suggest a vocabulary term | `ddp_tracker.representations.services.suggest_term(model, name, description, user)` |
| Make a suggestion as a non-staff user | `ddp_tracker.proposals.services.submit(user, kind, location=, values=, comment=)` |
| Which locations can have a representation | `ddp_tracker.representations.eligibility.eligible(locations)` |
| Type, format, first and last seen of locations | `ddp_tracker.schemas.profiles.profiles(location_ids, observations)` |
| New and changed data points of an upload | `ddp_tracker.schemas.timeline.new_in(upload)`, `timeline.change_details(upload)` |
| Uploads a user may open | `Upload.objects.visible_to(user)` |

## 6. Site behaviour

### 6.1 Home page and navigation

```
[logo] DDP Tracker        Home · Explore · Docs · (account items, unchanged)
Prototype previews:       Concepts · Compare · API · Curate (staff only)
```

- The brand and "Home" link to `journeys:index`.
- "Explore" stays exactly `<a href="/platforms/">Explore</a>` (an existing test matches it).
- The account items keep their markup: Uploads or My uploads, Approvals (N), Suggestions (N) or My suggestions, the "Upload a DDP" button, Log out.
- Signed-out visitors see "Contribute" (to the contributor's journey) and "Log in".
- The main row's element stays `<nav class="site-nav">` and must not contain the word "Representations" (an existing test checks both).
- The strip is a second `nav` with `aria-label="Prototype pages"`. The word "Curate" appears in it for staff only (an existing test checks that signed-out users and non-staff never see "Curate" on the overview page).

### 6.2 Landing page (`/`)

In this order:

1. `h1` "DDP Tracker", the sentence "Find out what platforms' data downloads contain, what it means, and how it changes." and two lines on how the tracker works and protects privacy.
2. `h2` "What brings you here?" and the eight role cards. A card has the role name (the link), "I want to …", and "N steps: X available today, Y prototype".
3. `h2` "How it works": four steps (Upload, Parse, Annotate, Explore).
4. `h2` "In this tracker today": four figures (platforms, uploads, data points, annotations), counted from the database.
5. A closing line with links to the overview page ("all tasks on one page") and the feature cards.

### 6.3 Journey page (`/journeys/<role>/`)

In this order: breadcrumb; `h1` the role name; "Aim"; "Who this is for"; a note if the database has no demo data; `h2` "Steps" with the numbered steps; `h2` "Features this journey needs" with the table; `h2` "Other journeys" with links to the seven others.

A step shows: its title with a badge (**Available** or **Prototype**, as text); its text; "Needs an account" or "Staff only today" where that applies; the main button; the "today" button and the "demo" button where present; and "Still missing: …" where present.

### 6.4 Mock-up pages

`03-site-structure.md` lists their content. The tasks in phases 3 and 4 give each page's data, behaviour and tests. Buttons that would change something either do something harmless and local (the shortlist) or answer with a message that starts "In the real feature, this would …".

## 7. The look

Match the current site: white, Bootstrap, dark navy (`#0D1C42`), system sans-serif. Reference screenshots: `../handoff-user-journeys/reference-screenshots/`.

The project's own Sass already restyles three Bootstrap names. Use them as the project does:

- `.card` is a plain bordered box with padding, inside `<ul class="cards">` (a responsive grid). `.card__title` is the bold link, `.card__hint` a small muted line.
- `.badge` is a small pill; colour comes from a modifier (`badge--done`, `badge--pii` …).
- `.container` is the page's main column (already around the content block).

Classes added by this work (all defined once, in `assets/scss/pages/_journeys.scss`, which task 2.2 copies from the starter files). Later tasks **reuse** them and add Sass only if nothing here fits.

| Class | Use |
|---|---|
| `prototype-nav`, `prototype-nav__label` | The strip under the header |
| `prototype-banner` | The banner on mock-up pages (with Bootstrap's `alert alert-warning`) |
| `prototype-footer` | "Where this fits" at the bottom of a mock-up |
| `badge--available`, `badge--exists` | Green pill |
| `badge--prototype`, `badge--partial` | Amber pill |
| `badge--gap` | Red pill |
| `badge--official` | Purple pill (official documentation). There is no "fictional" label: Hekmat decided at the Phase 3 check-in (30 September 2026) that pages carry no such tags; the banner says it once per page |
| `landing-hero` | The landing page's opening block |
| `role-card`, `role-card__line`, `role-card__meta` | Role cards |
| `how-it-works` | The four-step strip |
| `stat-tiles`, `stat-tile`, `stat-tile__value`, `stat-tile__label` | Figures |
| `journey-steps`, `journey-step`, `journey-step--prototype`, `journey-step__title`, `journey-step__missing` | Numbered steps |
| `role-switch` | Links to the other journeys |
| `chip`, `chip--on`, `chip--off`, `chip--active` | Small labels: platform availability, theme filters |
| `proto-columns` | A responsive grid of panels |
| `proto-panel` | A bordered panel with a light background |
| `proto-toolbar` | A row of filters or buttons that wraps |
| `table-scroll` | Wraps a wide table so that the table scrolls sideways, not the page |
| `matrix`, `matrix__yes`, `matrix__no` | The comparison matrix |
| `timeline`, `timeline__entry`, `timeline__date` | The changelog |
| `code-sample` | A block of JSON, CSV or a command |
| `endpoint`, `endpoint__method` | One API endpoint |
| `cite-box` | A citation to copy |
| `quiz` | The learner's questions (native `details` elements) |
| (no class) | A copy button: a normal Bootstrap button (`btn btn-secondary btn-sm`) with `data-copy="…"` and `data-copied="<what to announce>"`, plus an element `role="status" data-copy-status` near it; `journeys.js` copies the value and writes the outcome into that element. Never the class `copy-button`: the reviews app already styles it as a bare icon button (changed during the build, task 3.3) |

Accessibility rules: one `h1` per page; headings in order; link and button texts that make sense out of context (never "click here" or a bare "Go"); status never by colour alone; tables have `<th scope="col">`; every form control has a label (`visually-hidden` is fine); focus stays visible (Bootstrap's default); the page never scrolls sideways at 375 pixels wide.
