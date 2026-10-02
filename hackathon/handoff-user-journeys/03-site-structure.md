# 03. Site structure

Proposed by Claude and accepted as the plan (see `02-decisions.md`, D9 to D13). Names, URLs and layout details can be refined during design; record changes in the decision log.

## Navigation

```
Home · Explore · Concepts · Compare · Contribute · Curate (staff) · API · Docs      [account items]
```

| Item | Goes to | Real or prototype | Notes |
|---|---|---|---|
| Home | `/` (landing page, role picker) | Real (new) | Replaces the current home page |
| Explore | `/platforms/` (`schemas:platforms`) | Real (exists) | Unchanged |
| Concepts | `/prototype/concepts/` | Prototype | Concept view for researchers |
| Compare | `/prototype/compare/` | Prototype | Platform comparison |
| Contribute | `/uploads/new/` (`ddps:upload-create`) | Real (exists) | Today the nav shows "Upload a DDP" as a button; keep that button or rename |
| Curate | `/prototype/moderate/` for staff | Prototype | The existing staff items (Approvals, Suggestions) stay as they are |
| API | `/prototype/api/` | Prototype | |
| Docs | `/docs/` (`docs`) | Real (exists) | |
| Account items | Existing: My uploads, Approvals (N), Suggestions (N) or My suggestions, Log in / Log out | Real (exists) | Keep the existing logic in `ddp_tracker/templates/base.html` |

Mark prototype items subtly in the navigation (for example a small "prototype" badge), so users know before they click.

## Sitemap

### New real pages (app `journeys`)

| URL | Name (proposed) | Page |
|---|---|---|
| `/` | `journeys:index` | Landing page: "What brings you here?" with eight role cards |
| `/journeys/<role>/` | `journeys:journey` | One journey per role (slugs below) |

Role slugs:

- `researcher` (substantive researcher)
- `engineer` (research engineer)
- `policy` (policy stakeholder)
- `contributor`
- `curator` (curator or platform moderator)
- `admin` (instance administrator)
- `machine` (machine consumer)
- `learner`

### Existing real pages that journeys link to

| Page | URL name | URL |
|---|---|---|
| Platform list | `schemas:platforms` | `/platforms/` |
| Platform explorer | `schemas:platform` | `/platforms/<slug>/` |
| Annotation list per platform | `annotations:annotations` | `/annotations/platform/<slug>/` |
| Annotation detail | `annotations:annotation` | `/annotations/<pk>/` |
| Representation list | `representations:representations` | `/representations/` |
| Representations per platform | `representations:platform` | `/representations/platform/<slug>/` |
| Representation detail | `representations:representation` | `/representations/<pk>/` |
| Vocabulary | `representations:vocabulary` | `/representations/vocabulary/` |
| Upload form | `ddps:upload-create` | `/uploads/new/` |
| My uploads | `ddps:uploads` | `/uploads/` |
| Upload detail | `ddps:upload` | `/uploads/<pk>/` |
| Inspect held upload | `ddps:upload-inspect` | `/uploads/<pk>/inspect/` |
| Review of an upload | `reviews:review` | `/uploads/<pk>/review/` |
| Approvals (staff) | `ddps:approvals` | `/uploads/approvals/` |
| Suggestion queue, annotations (staff) | `proposals:annotations` | `/proposals/annotations/` |
| Suggestion queue, representations (staff) | `proposals:representations` | `/proposals/representations/` |
| My suggestions | `proposals:mine` | `/proposals/mine/` |
| Django admin | `admin:index` | `/admin/` |
| Documentation | `docs` | `/docs/` |
| Health check | `core:health` | `/health/` |

Links that need a platform should use a seeded platform (for example TikTok) or let the user pick one.

### New prototype pages (all under `/prototype/`)

Every prototype page shows a banner at the top: **"Prototype: this page shows fictional data to illustrate a planned feature. It does not work yet."** It also links back to the journey(s) that use it and to the relevant section of the features analysis.

| # | URL | Name (proposed) | For roles | Feature (features analysis section) |
|---|---|---|---|---|
| M1 | `/prototype/concepts/` | `journeys:concepts` | Researcher, learner, policy | Concept view, field-specific ontology, relevance sorting, availability at a glance (4.1) |
| M2 | `/prototype/concepts/<slug>/` | `journeys:concept` | Researcher | Concept detail with platforms, meaning, availability, "add to shortlist" (4.1) |
| M3 | `/prototype/shortlist/` | `journeys:shortlist` | Researcher, engineer | Study shortlist, codebook export, DDM blueprint export (4.1, 4.2) |
| M4 | `/prototype/compare/` | `journeys:compare` | Policy, researcher | Platform comparison on disclosure (4.3) |
| M5 | `/prototype/platforms/<slug>/changes/` | `journeys:changes` | Engineer, policy | Platform-level changelog (4.2, 4.3) |
| M6 | `/prototype/api/` | `journeys:api` | Machine consumer, engineer | Read-only API, exports, LLM access (4.7) |
| M7 | `/prototype/snapshots/` | `journeys:snapshots` | Policy, researcher, machine | Versioned, citable snapshots and licence (4.1, 4.3, 4.7) |
| M8 | `/prototype/request/<slug>/` | `journeys:request` | Contributor | Platform-specific instructions for requesting a DDP (4.4) |
| M9 | `/prototype/moderate/` | `journeys:moderate` | Curator | Moderator dashboard scoped to platforms (4.5) |
| M10 | `/prototype/moderate/seed/` | `journeys:seed` | Curator | Seeding annotations from official documentation (4.5) |
| M11 | `/prototype/admin/roles/` | `journeys:roles` | Admin | Role and platform management outside the Django admin (4.6) |
| M12 | `/prototype/learn/<slug>/` | `journeys:learn` | Learner | "What this platform keeps about you" and a guided exercise (4.8) |

## Page specifications

### Landing page (`/`)

- **Headline:** what the DDP Tracker is, in one sentence: "Find out what platforms' data downloads contain, what it means, and how it changes." Then a question: "What brings you here?"
- **Eight role cards**, each with:
  - the role name;
  - a one-line "I want to …" (below);
  - the number of steps;
  - how many steps are available today versus prototype.

  Each card links to its journey.
- **A short "How it works" strip:** upload, parse, annotate, explore (reuse the four steps from `docs/docs/index.md`).
- **Live counts:** platforms, uploads, data points, annotations. The current home page and platform list already compute similar numbers.
- **Accessible:** real headings, cards as links with clear text, good contrast, works at phone width.
- Works for anonymous users. Signed-in users may see a "continue" hint (optional).

| Role | Card line ("I want to …") |
|---|---|
| Substantive researcher | find which platform data can answer my research question |
| Research engineer | know exactly where each variable is and how to extract it |
| Policy stakeholder | see what platforms disclose and how that changes |
| Contributor | donate the structure of my own data download safely |
| Curator or moderator | describe what data points mean and keep a platform up to date |
| Instance administrator | set up and run a DDP Tracker |
| Machine consumer | read schemas and annotations in a stable format |
| Learner | understand what a platform keeps about me |

### Journey page (`/journeys/<role>/`)

- **Top:**
  - role name;
  - the role's goal (one or two sentences);
  - "Who this is for";
  - links to switch to other roles.
- **Steps**, as a numbered vertical list. Each step has:
  - a title;
  - one or two sentences on what you do and why;
  - a status badge (**Available** or **Prototype**);
  - a primary link ("Go to …");
  - optionally, "what's still missing".
- **Bottom:** "Related features", linking to the features analysis or listing the gaps this journey exposes.
- **Store journeys as data**, not hand-written templates: a Python module (for example `journeys/content.py`) with a list of roles and steps, rendered by one template. This keeps them easy to edit and testable (for example, a test that every step's URL resolves).

### Mock-up pages (M1 to M12)

General rules:

- Use Bootstrap components (cards, tables, list groups, badges, nav tabs). No inline styles or scripts; put any styles in `assets/scss/pages/` and any JavaScript in `ddp_tracker/static/js/`.
- Prefer **real seeded data where it exists**, with prototype-only fields (themes, relevance, official documentation text) from a fixed Python module. Example: the concept view can list real representations and annotations from the seeded database, with fictional themes attached.
- Buttons that would change something (Add to shortlist, Export, Approve) either:
  - do something harmless and local (for example keep the shortlist in the session); or
  - show a message: "In the real feature, this would …".
- Every page has the prototype banner.

| # | Content |
|---|---|
| M1 Concepts | **Filters:** research theme (field-specific labels such as "News and politics", "Health", "Social ties", "Advertising", "Wellbeing"), platform, language.<br>**Sort:** relevance (fictional usage scores) or name.<br>**Concept cards:** name (for example "Watched a video", "Searched", "Liked a post", "Sent a message", "Logged in", "Saw an ad"); plain description; platform availability chips; first and last seen; number of uploads; PII flag; "Add to shortlist".<br>A toggle "Show full structure" links to the explorer (the "without annotation mask" idea). |
| M2 Concept detail | **Per platform:**<br>- path(s);<br>- type and format;<br>- time zone note (`tz_whos`, for example "UTC" for TikTok);<br>- example values as a **table with title and value** (hackathon request);<br>- languages seen.<br>Also: a representation summary (actor · activity · object) and "Add to shortlist". |
| M3 Shortlist | **Table of chosen concepts:** platform, path, type, format, why chosen (note).<br>**Buttons:** "Share with an engineer" (copy link), "Download codebook (CSV)", "Download DDM File Blueprint (JSON)".<br>Show a preview of both exports on the page. If the export is generated from real seeded data, even better. |
| M4 Compare | **Matrix:** platforms (columns) × concepts (rows), with a mark where a platform discloses the concept.<br>**Summary per platform:** request modes, formats, documentation available, machine-readability. |
| M5 Changes | **Timeline per platform:** request dates, with added, changed and removed data points. With `seed_demo`'s second TikTok upload this can be real, computed from observations. A fixed fictional timeline is acceptable. |
| M6 API | **Endpoint list:** platforms, data points, profiles, annotations, representations, vocabulary, exports; each with an example request and JSON response.<br>**Also:** note that `django-ninja` is already a dependency; a section on LLM access (`llms.txt`, MCP); the licence. |
| M7 Snapshots | **List of monthly releases:** date, counts, a DOI placeholder clearly marked fictional, and a "Cite this" box (APA-style text). |
| M8 Request instructions | **Steps to request a DDP from the platform:** generic but plausible, and marked "to be verified by curators". |
| M9 Moderator dashboard | **"Your platforms"** (fictional assignment: TikTok, Instagram).<br>**Per platform:** untriaged data points, open suggestions, uploads awaiting approval, missing annotations. Link to the real queues.<br>**A card:** "Seed from official documentation". |
| M10 Seed from documentation | Side by side:<br>- official documentation entries (fictional text, marked as "official" source);<br>- matched observed data points.<br>Show gaps both ways ("documented but not observed", "observed but not documented") and "Accept as annotation" buttons. |
| M11 Roles | **Users × roles table:** administrator, moderator (with platforms), curator, contributor.<br>**Platforms list** with an "Add platform" form.<br>**Path rules list.** |
| M12 Learn | "What <platform> keeps about you":<br>- categories in plain language (activity, messages, ads, device and login, profile), with counts from the seeded upload;<br>- one example data point explained;<br>- a short guided exercise with 3 questions. |
