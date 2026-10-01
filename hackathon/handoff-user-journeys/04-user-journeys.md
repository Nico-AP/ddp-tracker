# 04. User journeys

Eight journeys, one per role.

- **Status:** **A** = Available (the linked page exists and does the job today); **P** = Prototype (link to a mock-up page, see `03-site-structure.md`).
- **"Feature"** refers to the section of `../DDP-Tracker_features-by-role.md`.
- Wording is a draft: tighten it during design, but keep the substance.

## 1. Substantive researcher (`researcher`)

**Goal:** find which platform data can answer my research question, understand what it means, and hand a precise list to the person who builds the extraction.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Pick your research theme | Choose a field-specific theme (for example "News and politics") to filter concepts | M1 `journeys:concepts` (theme filter) | P | 4.1 field-specific ontology |
| 2 | Browse concepts across platforms | See concepts relevant to the theme, sorted by relevance, with platform availability | M1 `journeys:concepts` | P | 4.1 concept view, relevance sorting |
| 3 | Understand a concept | Read what it means, where it appears, since when, in which languages, with example values | M2 `journeys:concept`; the real equivalent is `annotations:annotation` and `representations:representation` | P (partly A) | 4.1 |
| 4 | Build a study shortlist | Add the concepts you need, with a note on why | M3 `journeys:shortlist` | P | 4.1 shortlist |
| 5 | Hand over to your engineer | Share the shortlist or download a codebook | M3 `journeys:shortlist` (share, CSV) | P | 4.1 codebook export |

## 2. Research engineer (`engineer`)

**Goal:** know exactly where each variable is, in which format and variants, and get machine-readable specifications to build extraction code from.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Open the researcher's shortlist | See the chosen concepts with their paths | M3 `journeys:shortlist` | P | 4.1, 4.2 |
| 2 | Inspect exact paths, types and formats | Use the full tree, the side panel profile and the JSON outline | `schemas:platform` (for example TikTok) | A | 4.2 |
| 3 | Check variants and history | Filter by language, date and format; read a data point's per-upload history | `schemas:platform` with filters | A | 4.2 |
| 4 | See what changed recently | Read the platform changelog | M5 `journeys:changes` | P | 4.2 changelog |
| 5 | Download specifications | Get a JSON Schema, a CSV codebook, or a DDM File Blueprint | M3 `journeys:shortlist` (exports), M6 `journeys:api` | P | 4.2 exports |

## 3. Policy stakeholder (`policy`)

**Goal:** see what platforms disclose, compare them, follow changes, and cite a fixed state.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Choose platforms | Pick the platforms to look at | `schemas:platforms` | A | 4.3 |
| 2 | Compare what they disclose | Read the concepts-by-platforms matrix and platform summaries | M4 `journeys:compare` | P | 4.3 comparison |
| 3 | Follow changes over time | See what each platform added, changed or removed | M5 `journeys:changes` | P | 4.3 timeline |
| 4 | Cite a snapshot | Pick a dated release and copy its citation | M7 `journeys:snapshots` | P | 4.3 snapshots |

## 4. Contributor (`contributor`)

**Goal:** donate the structure of my own data download safely, and see what it added.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Request your data from the platform | Follow platform-specific instructions | M8 `journeys:request` | P | 4.4 instructions |
| 2 | Read what happens to your data | Understand parse-then-delete and anonymisation | `docs` (`/docs/guide/privacy/`) | A | 4.4 |
| 3 | Upload your DDP | Fill in the upload form (needs an account) | `ddps:upload-create` | A | 4.4 |
| 4 | Check it before it counts | Inspect a held upload: known, matched, new, missing | `ddps:upload` then `ddps:upload-inspect` | A | 4.4 |
| 5 | See what your upload added | Read the review: New, Known, Changed, Missing | `reviews:review` | A | 4.4 |

## 5. Curator or platform moderator (`curator`)

**Goal:** keep a platform's knowledge up to date: describe new data points, decide on suggestions, and seed from official documentation.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Open your platforms dashboard | See queues for the platforms you moderate | M9 `journeys:moderate` | P | 4.5 platform-scoped roles |
| 2 | Triage new data points | Link to an annotation, create one, or mark "not a data point" | `schemas:platform` with "missing annotations", then the triage dialog | A | 4.5 |
| 3 | Describe representations | Add what a list's items mean in the shared vocabulary | `representations:platform` and the explorer's side panel | A | 4.5 |
| 4 | Decide on suggestions | Accept or reject others' suggestions (staff today) | `proposals:annotations` | A (staff only) | 4.5 |
| 5 | Seed from official documentation | Match platform documentation with observed data points | M10 `journeys:seed` | P | 4.5 seeding |

## 6. Instance administrator (`admin`)

**Goal:** set up and run a tracker: platforms, path rules, roles, retention, health.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Add platforms and path rules | Manage them in a friendly interface | M11 `journeys:roles`; today: `admin:index` | P (A in the Django admin) | 4.6 |
| 2 | Assign roles and moderators | Give people roles scoped to platforms | M11 `journeys:roles` | P | 4.6 roles |
| 3 | Approve new vocabulary terms | Approve suggested terms | `admin:index` (vocabulary models) | A (Django admin) | 4.5 vocabulary governance |
| 4 | Check health and retention | Health check; scheduled deletion of uploader values | `core:health`; docs on `purge_upload_values` | A (partial) | 4.6 |

## 7. Machine consumer (`machine`)

**Goal:** read schemas and annotations in a stable, documented format.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Read the API overview | See endpoints, formats and examples | M6 `journeys:api` | P | 4.7 API |
| 2 | Fetch a platform's schema | Example request and response | M6 `journeys:api` (anchor) | P | 4.7 |
| 3 | Pin a snapshot | Use a versioned release for reproducibility | M7 `journeys:snapshots` | P | 4.7 versions |
| 4 | Connect an LLM | `llms.txt` or an MCP server over the API | M6 `journeys:api` (anchor) | P | 4.7 LLM access |

## 8. Learner (`learner`)

**Goal:** understand what a platform keeps about me, in plain language, and learn to read a DDP.

| # | Step | What the user does | Target | Status | Feature |
|---|---|---|---|---|---|
| 1 | Pick a platform you use | Choose from the platform list | `schemas:platforms` | A | 4.8 |
| 2 | See what it keeps about you | Read plain-language categories | M12 `journeys:learn` | P | 4.8 summaries |
| 3 | Look at one data point closely | Open a data point with its explanation and examples | `schemas:platform` (side panel) | A | 4.8 |
| 4 | Try a guided exercise | Answer three questions about a DDP | M12 `journeys:learn` (exercise section) | P | 4.8 teaching |

## Checks for the journeys

- Every step's target must resolve (write a test that reverses every URL name used in `content.py`).
- Available steps must link to pages that load for the role's typical user:
  - anonymous for researcher, policy, learner and machine consumer;
  - signed in for contributor;
  - staff for curator and administrator.

  Where a page needs a login or staff rights, say so in the step text ("needs an account", "staff only today").
- Keep each journey to 3 to 5 steps.
