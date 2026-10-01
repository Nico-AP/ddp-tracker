# DDP Tracker: features by user role

Infrastructure track, DDP2026 Hackathon. Conceptual draft for discussion, version 2, 30 September 2026.

## 1. Purpose and how to read this

This document maps what the DDP Tracker does today onto the user groups named in the hackathon document, and lists the features each group still needs. Today's focus is the two researcher roles, the substantive researcher and the research engineer, including uses in education, so those sections are the most detailed. It is meant as a starting point for the infrastructure track to prioritise from, not as a finished specification.

The inventory of existing features comes from the `dev` branch of the repository (commit a18b3f3). The needs come from the hackathon document, the tracker's documentation, the Data Donation Lab website, and the Data Donation Module paper (Pfiffner, Witlox and Friemel, 2024).

Each feature carries a status:

- **Exists**: available in the tool today.
- **Partial**: some of it exists, or it exists only for staff or through the Django admin.
- **Gap**: not in the tool today.

Features first raised in the hackathon document are marked *(hackathon)*.

Section 7 turns the researcher-facing gaps into feature cards in the hackathon's template, ready to paste into the shared document.

## 2. User roles

The hackathon document names researchers interested in concepts, researchers setting up parsing, policy people, participants and students, and machine readers (API endpoints for researchers and LLMs). Contributing and curating DDPs also imply contributor, curator and administrator roles. That gives eight roles.

| Role | Who | Core question they bring |
|---|---|---|
| Substantive researcher | Social scientists designing a data donation study | Which data in which platforms can answer my research question, and what does it mean? |
| Research engineer | People who build parsers, extraction scripts and donation pipelines (for example in DDM or Port) | Exactly where is each variable, in what format, and how does that vary across languages, formats and time? |
| Policy stakeholder | Regulators, data protection bodies, NGOs, journalists | What do platforms disclose, how does it compare, and how does it change? |
| Contributor | Anyone who uploads a DDP, including study participants | Is my upload safe, and did it help? |
| Curator or platform moderator | Experts who annotate data points and define representations for one or more platforms | What is new or changed, and what does it mean? |
| Instance administrator | People who run and maintain a tracker instance | How do I configure platforms, roles, retention and deployments? |
| Machine consumer | Scripts, other tools (DDM, Port), LLM agents | Can I read the schema and annotations in a stable, documented format? |
| Learner | Participants, students, teachers, the general public | What does a platform know about me, and how do I work with it? |

### How these map onto the code today

The code has only three permission tiers: **anonymous**, **signed in**, and **staff** (`is_staff`). Two further rights depend on the object: an uploader can manage their own upload, and a proposer can withdraw their own suggestion. Django groups and model permissions are not used anywhere in the app code; superuser status only matters inside the Django admin.

| Hackathon role | Closest tier in the code today |
|---|---|
| Substantive researcher, policy stakeholder, learner | Anonymous (all exploring is public) |
| Research engineer | Anonymous, plus the parser CLI run locally |
| Contributor | Signed in, as uploader of their own uploads |
| Curator or platform moderator | Signed in non-staff users can only *suggest*; staff apply changes directly |
| Instance administrator | Staff plus Django admin (superuser) |
| Machine consumer | None: there is no API |

So all curators are either global staff or suggesters. There is no role scoped to a platform, and no distinction between a researcher and any other visitor.

## 3. What the tool does today

| Area | Feature | Who can use it |
|---|---|---|
| Upload | Upload a DDP (ZIP, JSON or CSV, up to 2 GB) with platform, request date, request mode (app, browser or Portability API), request format and account language | Signed in |
| Upload | Background parsing into a schema document; raw file always deleted afterwards | Automatic |
| Upload | Plausibility checks: duplicate detection, first-of-its-kind approval, similarity threshold with uploader confirmation | Uploader, staff |
| Upload | Inspect a held upload (known, matched, new and missing data points) before it is registered | Uploader, staff |
| Privacy | Anonymised file names; variable keys (IDs, usernames), look-alike folders and media file names replaced with `{*}` | Automatic |
| Privacy | Uploader's own sample values (up to 5 per data point, emails masked), encrypted, readable only by the uploader for 3 days | Uploader |
| Explore | Platform list with counts; platform explorer with the full data point tree | Everyone |
| Explore | Filters by request date range, language, request format and root format; text search within a platform; "missing annotations" and "missing representations" views | Everyone |
| Explore | Side panel per data point: annotation, examples, representations, profile (types, shapes, formats including date formats with or without a time zone marker, first and last seen), JSON outline, per-upload history | Everyone |
| Review | Review of an upload in tabs New, Known, Changed and Missing, with before and after values | Uploader, staff |
| Curation | Triage: link to an annotation, create an annotation, mark as "not a data point", reset; annotate similar moved or renamed paths together | Signed in (suggest), staff (apply) |
| Curation | Annotations (name, description, note, PII flag) spanning several locations; list and detail pages | Everyone reads; signed in suggests; staff applies |
| Curation | Representations of list items using a shared vocabulary (actor, activity, object, target) with metadata links | Everyone reads; signed in suggests; staff applies |
| Curation | Vocabulary page; suggest new terms | Everyone reads; signed in suggests; admin approves |
| Curation | Example values per data point, edited directly with no review step | Signed in |
| Governance | Suggestion workflow with staff queues, stale detection, accept or reject with reason, "My suggestions"; a new suggestion on the same target replaces one's own open one | Signed in, staff |
| Governance | Approvals queue for held uploads | Staff |
| Admin | Create platforms, path rules (which keys to rename or keep), approve vocabulary, manage users (Django admin only) | Admin |
| Docs | User guide and technical reference (MkDocs) served at /docs/ | Everyone |
| Developer | Parser library and command-line tool that outputs the schema document as JSON; reads ZIP, JSON, JSONL, CSV and X's `.js` files, with HTML and TXT planned | Developers, locally |

What is **not** there today is just as important for this track:

- no API (`django-ninja` is a dependency but no code uses it);
- no export of any kind;
- no HTML parsing;
- no search across platforms;
- no notifications;
- no roles below global staff;
- no versioned releases of the knowledge base.

## 4. Features needed by role

### 4.1 Substantive researcher

The researcher needs a digestible, concept-first view: what exists that is relevant to their question, what it means, and whether it is available on the platforms and in the period they care about.

| Feature | Status | Notes |
|---|---|---|
| Browse annotated variables per platform with plain-language descriptions | Exists | Annotation list and detail pages |
| Compare the same concept across platforms | Partial | Representations and a shared vocabulary exist; there is no side-by-side comparison view |
| Field-specific top-level ontology, so each research area can label variables in its own terms *(hackathon)* | Gap | The current vocabulary is one shared set of actor, activity and object types; a layer of discipline labels on top of annotations would let communication science, health and economics each see their own grouping |
| Search by concept or label across all platforms | Gap | Search is per platform and matches names and paths only |
| Sort data point lists by relevance or how often they are used *(hackathon)* | Gap | The tree is alphabetical; usage could come from how often a data point appears in uploads (already counted) or from how many studies shortlist it |
| Prioritise which annotations matter most *(hackathon)* | Gap | Relevance signals above would also tell curators where to spend effort |
| Default public page versus a user or community page *(hackathon)* | Gap | Today everyone sees the same explorer; the hackathon asks whether the public default should be a curated view, with the full tree "without an annotation mask" one click away |
| "Annotated only" view that hides structural and unannotated nodes | Partial | The explorer has the inverse filter ("missing annotations") |
| Availability at a glance: platforms, languages, formats, first and last seen, number of uploads | Partial | Shown per data point in the profile; not summarised per annotation or concept |
| Examples shown as a table of title and value, with labels that can be annotated *(hackathon)* | Partial | Examples exist as a flat list per data point |
| Meaning of timestamps: whose time zone a timestamp represents *(hackathon)* | Partial | The parser already records whether a date format carries a time zone marker (`Z` or an offset); whose time a naive timestamp shows is not recorded (the `tz_whos` proposal) |
| Sensitivity information for ethics applications | Partial | A PII flag exists per annotation; no finer sensitivity levels or ethics summary |
| Study shortlist ("basket") of chosen variables, shareable with an engineer | Gap | The bridge between the two views (see section 5) |
| Codebook export of the shortlist | Gap | |
| Citable, versioned reference for methods sections and preregistrations | Gap | |
| Teaching material: guided tours of a platform's DDP for students *(hackathon: education)* | Gap | Could reuse representations and examples |

### 4.2 Research engineer

The engineer needs the exhaustive, structure-first view: every path, type and format, all the variants, and machine-readable outputs they can build parsers and extraction code from.

| Feature | Status | Notes |
|---|---|---|
| Full data point tree with types, shapes, formats and lengths | Exists | Explorer, profile and JSON outline |
| Variants by request format, language and request date | Exists | Schema filters and per-upload history |
| Explain what a `{*}` segment stands for (for example "variable key: dates", "look-alike folders", key count) *(hackathon)* | Partial | The parser collapses such segments and records how many keys were merged, but the explorer does not say what kind of values to expect in their place |
| Language flag on data points, and matching of paths across languages *(hackathon)* | Partial | Uploads carry the account language and the parser suggests translated keys; there is no language flag per data point or a curated path dictionary |
| Recognise "no data" markers (for example "No data available", "there is no data for this") *(hackathon)* | Gap | Would need a curated list of sentinel strings per platform, flagged on the data point |
| HTML DDPs, including their date and time conventions *(hackathon)* | Gap | HTML is planned in the parser specification but not implemented |
| Paired donation sets (uploads that differ in one aspect only, such as language or HTML versus JSON) *(hackathon)* | Gap | See the feature card in section 7 |
| Compare official platform documentation with actual DDPs *(hackathon)* | Gap | Depends on importing documentation (see 4.5) |
| Platform-level changelog, or a diff between two dates | Partial | New, Changed and Missing exist per upload review; not per platform or between arbitrary dates |
| Watch a platform or variable and get notified of changes | Gap | |
| Machine-readable schema export (JSON Schema, CSV codebook) | Gap | The parser specification notes a JSON Schema exporter would be straightforward |
| Extraction specification for donation tools (for example DDM File Blueprints: file name pattern, required fields, fields to keep; Port extraction stubs) | Gap | Highest-leverage link to the DDM |
| Read-only API *(hackathon)* | Gap | See 4.7 |
| Run the parser locally on a test DDP | Exists | Command-line tool, developer oriented |
| Synthetic test DDPs generated from the schema | Gap | Useful for testing pipelines without real data |

### 4.3 Policy stakeholder

| Feature | Status | Notes |
|---|---|---|
| Public, no-account overview of what each platform discloses | Exists | |
| Platform-level timeline of what was added, changed or removed | Partial | The data is there (observations by request date); there is no view for it |
| Gaps between what platforms document and what their DDPs contain *(hackathon)* | Gap | A direct accountability measure once documentation is imported |
| Comparison of platforms on disclosure (coverage of concepts, machine-readability, documentation, request modes) | Gap | Would build on representations and upload metadata |
| Reports and citable snapshots that can serve as evidence | Gap | Depends on versioning |

### 4.4 Contributor (uploader)

| Feature | Status | Notes |
|---|---|---|
| Upload with privacy by design (parse, then delete; anonymised names; encrypted own values) | Exists | |
| Record how the DDP was obtained, including routes outside the three fixed options *(hackathon)* | Partial | Request mode is limited to app, browser or Portability API; the hackathon asks for an "Other" option with free text (for example ChatGPT's privacy centre) |
| Platform-specific instructions for requesting a DDP | Gap | The upload guide gives generic advice only |
| Clear review of one's own upload *(hackathon)* | Partial | An upload with the earliest request date shows everything as "new", because comparison is only with earlier requests |
| Assurance that identifying path segments are removed *(hackathon)* | Partial | Heuristics and path rules exist, but the TikTok chat case shows a username can still get through (see the appendix) |
| Notification when an upload is approved or rejected | Gap | Users must check the upload page |
| Recognition of contributions | Gap | |

### 4.5 Curator or platform moderator

| Feature | Status | Notes |
|---|---|---|
| Triage, annotate, define representations | Exists | |
| Suggestion queues, stale detection, approvals queue | Exists | Staff only |
| Edit one's own open suggestion *(hackathon)* | Partial | Submitting a new suggestion on the same target replaces the old one; there is no edit-in-place |
| Seed annotations from official platform documentation, as a separate annotation kind *(hackathon)* | Gap | Annotations have one kind today; an "official documentation" source, with its own provenance, would keep platform claims apart from curator descriptions |
| Seed annotations from HTML and JSON pairs, and from AI-suggested labels checked by people *(hackathon)* | Gap | HTML pairs need HTML parsing first |
| Moderator role scoped to one or more platforms ("DDP hubs") *(hackathon)* | Gap | Only global `is_staff` today |
| Translations of field names and descriptions, building a multilingual dictionary *(hackathon)* | Gap | Language filters and translated-key suggestions exist |
| Review step for example values | Gap | Examples change directly, by design |
| Vocabulary governance in the app | Partial | Term approval is in the Django admin only |
| Audit trail of curation decisions | Partial | Proposal history, read-only in the admin |

### 4.6 Instance administrator

| Feature | Status | Notes |
|---|---|---|
| Add platforms and path rules | Partial | Django admin only |
| Manage roles beyond staff | Gap | Depends on the role model in 4.5 |
| Scheduled deletion of expired uploader values | Partial | The `purge_upload_values` command exists; no schedule was found in the deployment configuration |
| Correct site domain in account emails *(hackathon)* | Gap (bug) | Emails refer to example.com; `django.contrib.sites` is enabled but the site domain is never set |
| Federation or several hubs sharing one knowledge base *(hackathon)* | Gap | Governance question |
| Health check | Exists | `/health/` |

### 4.7 Machine consumer (scripts, tools and LLMs)

| Feature | Status | Notes |
|---|---|---|
| Read-only API for platforms, data points, profiles, annotations, representations and vocabulary *(hackathon)* | Gap | `django-ninja` is already a dependency and would also generate OpenAPI documentation |
| Standard export formats (JSON Schema, CSV, codebook) | Gap | |
| Stable identifiers and versions | Partial | Database IDs and slugs exist; no versioned releases |
| LLM-friendly access (for example an `llms.txt` file or an MCP server over the API) | Gap | |
| Clear licence for the schema knowledge base | Gap | The code is GPL-3.0; no licence is stated for the curated annotations and representations |

### 4.8 Learner

| Feature | Status | Notes |
|---|---|---|
| Public exploring and a plain user guide | Exists | |
| Simplified summaries per platform ("what this platform keeps about you") | Gap | Could reuse representations |
| Guided exercises for teaching *(hackathon: education)* | Gap | Shared with 4.1 |

## 5. Tensions to resolve

**Exhaustive versus digestible.** This runs through most of the tables above. Research engineers need every path, variant and format. Substantive researchers need a short, meaningful list tied to their research question. The data model already supports both, because descriptive facts are kept per upload and curation is kept separately. The difference lies in what each view shows.

A workable principle is **two views, one model, and a hand-off between them**:

- The *concept view* starts from annotations and representations. It groups them by the field-specific ontology, sorts by relevance, hides structural nodes, and shows availability at a glance. This is a candidate for the default public page.
- The *structure view* is the current explorer "without an annotation mask", extended with explanations of `{*}` segments, language flags, changelogs and exports.
- A *study shortlist*, built in the concept view, is exported from the structure view as a codebook and an extraction specification. This is the hand-off, and how often variables are shortlisted can feed the relevance sorting.

The researcher never has to see the full tree, and the engineer never has to reconstruct what the researcher meant.

**One ontology versus many.** A shared vocabulary makes cross-platform comparison possible, but each research area wants its own labels. A layered design keeps both: the shared vocabulary stays the backbone, and field-specific labels map onto it rather than replacing it.

**Official documentation versus observed reality.** Seeding from platform documentation saves a great deal of curation work, but documentation and actual DDPs differ, and that difference is itself a finding. Keeping official annotations as a separate kind, rather than merging them into curator annotations, preserves the gap as data.

**Open contribution versus quality.** Anyone signed in can suggest, and staff decide. That is safe, but it concentrates work on a few people and will not scale across many platforms. Platform-scoped moderators, AI-assisted seeding and a review step for examples would each shift this balance, and each needs a governance decision.

**Privacy versus usefulness.** The same anonymisation rules both over-reach and under-reach. The hackathon document reports a Facebook folder collapsed to `{*}` that engineers need to understand, and a TikTok username left in a path. Example values help researchers but carry risk. Per-platform path rules and a documented review process may be needed, not only better heuristics.

**Living knowledge versus citable stability.** The tracker is always changing, but research and policy need to cite a fixed state. Versioned snapshots, for example monthly releases with a DOI, would serve both.

**Central versus federated governance.** The hackathon document suggests separate hubs responsible for single platforms, each with its own moderators. That affects the role model, the API and deployment, so it is worth settling early.

## 6. Suggested priorities for the infrastructure track

These are proposals for discussion, ordered by how much other work depends on them.

1. **Fix the TikTok privacy issue now.** It needs a path rule in the admin, not new code (see the appendix).
2. **Role model.** Replace the single staff tier with roles: platform moderator (scoped to platforms), curator, administrator. Most governance features depend on it.
3. **Read-only API and exports.** Expose the existing model through `django-ninja`: JSON Schema per platform, a CSV codebook, and a DDM File Blueprint export. This serves engineers, machine consumers and policy users at once.
4. **Annotation provenance and seeding.** Add an annotation kind (or source) for official platform documentation, so seeding can start while keeping platform claims apart.
5. **Concept view, field-specific labels and study shortlist.** The researcher-facing counterpart to the explorer, and the hand-off to engineers.
6. **Data point attributes for engineers:** `tz_whos`, a language flag, "no data" markers, and an explanation for `{*}` segments.
7. **Versioned snapshots** of the knowledge base, so exports and citations point to a fixed state.
8. **Parser: HTML support**, which unlocks HTML and JSON pairs and HTML date conventions.
9. **Smaller fixes:** site domain in emails, an "Other" request mode with free text, scheduled purge of uploader values, platform and path rule management outside the Django admin, upload notifications, and editing one's own suggestions.

## 7. Feature cards in the hackathon template

These follow the template in the hackathon document. The first two add a technical implementation to the cards already there.

### Timezone specification (technical implementation added)

| Field | Content |
|---|---|
| Title | Timestamp entities need to clarify what time is captured |
| Problem | Platforms provide timestamps with or without time zone information, and it is not always clear whose time a naive timestamp shows |
| Description of Solution | A time zone attribute on date data points, labelled by curators, complementing what the parser already detects |
| User group | Substantive researchers, research engineers |
| Technical Implementation | The parser already records each date format, including whether it carries `Z` or an offset. Add a `tz_whos` field on the annotation (choices: UTC, user's local time, server time, platform-defined zone, unknown), editable through the normal suggestion workflow. Show it next to the detected format in the profile. Pre-fill "UTC" where every observed format carries `Z` (TikTok, per the hackathon notes, looks like UTC) |

### Paired donation sets (technical implementation added)

| Field | Content |
|---|---|
| Title | Paired donation sets |
| Problem | Annotating each format, language or download route of the same file separately is slow and can be inconsistent |
| Description of Solution | Link uploads that differ in only one aspect, so their schemas can be aligned and annotations carried across |
| User group | All |
| Technical Implementation | Add an optional pairing between uploads (a pair set with a "differs in" field: language, format, request mode). Uploader values are deleted after 3 days and never public, so alignment cannot rely on stored values. It can use what is kept: matching list lengths and counts, types, shapes and positions in the tree. The uploader could confirm matches while their own sealed values are still available. JSON and CSV pairs can start now; HTML pairs need HTML parsing first |

### Field-specific top-level ontology

| Field | Content |
|---|---|
| Title | Field-specific labels for variables |
| Problem | Researchers in different fields look for the same data under different concepts, and one shared vocabulary cannot serve them all |
| Description of Solution | Research areas maintain their own label sets that map onto annotations and the shared vocabulary |
| User group | Substantive researchers, learners |
| Technical Implementation | New models for an ontology (per field) and its labels, with a many-to-many link to annotations. Filter and group the concept view by ontology. Labels are suggested and approved through the existing proposal workflow |

### Relevance sorting

| Field | Content |
|---|---|
| Title | Sort data points by relevance or use |
| Problem | Alphabetical trees hide the variables that matter most, and curators do not know where to start |
| Description of Solution | Offer sorting by how often a data point is present across uploads and by how often researchers select it |
| User group | Substantive researchers, curators |
| Technical Implementation | Presence across uploads can be computed from existing observations. Selection counts need the study shortlist feature. Add a sort option to the explorer and annotation lists |

### Examples as a table

| Field | Content |
|---|---|
| Title | Show example values as a table with title and value |
| Problem | A flat list of example values makes it hard to see which value belongs to which field |
| Description of Solution | For objects and list items, show examples as rows of sibling fields, and allow labelling individual values |
| User group | Substantive researchers, research engineers |
| Technical Implementation | Examples are stored per data point today. Group examples of sibling data points under their parent list item and render them as one table. Labels on specific values would need a small addition to the example structure (a label per value) |

### Official documentation as an annotation source

| Field | Content |
|---|---|
| Title | Seed annotations from platform documentation |
| Problem | Annotating every data point by hand is labour-intensive, and platforms often document their DDPs already |
| Description of Solution | Import official documentation as a separate annotation kind, and flag where it disagrees with observed DDPs |
| User group | Curators, substantive researchers, policy stakeholders |
| Technical Implementation | Add a source field to annotations (curator or official), with a link to the source document and retrieval date. Show both where they exist. A "documented but never observed" and "observed but undocumented" report falls out of comparing them with observations |

### "No data" markers

| Field | Content |
|---|---|
| Title | Recognise values that mean "no data" |
| Problem | Platforms fill empty fields with phrases such as "No data available", which parsers mistake for real values |
| Description of Solution | Maintain a per-platform list of such markers and flag data points where they occur |
| User group | Research engineers |
| Technical Implementation | A curated list per platform (and language), applied by the parser when computing shapes, so marker values count as empty. Show a flag in the profile. Include the list in exports |

### "Other" request mode

| Field | Content |
|---|---|
| Title | Allow other ways of obtaining a DDP |
| Problem | Request mode only offers app, browser or Portability API, but some DDPs come through other routes (for example ChatGPT's privacy centre) |
| Description of Solution | Add an "Other" option with a free-text description |
| User group | Contributors, research engineers |
| Technical Implementation | Add a choice and a text field to the upload model and form; staff can later promote frequent answers to new fixed choices |

## Appendix: hackathon issues mapped to the code

| Issue from the hackathon document | Where it comes from in the code |
|---|---|
| TikTok chat history not anonymised (`.../ChatHistory/Chat History with <username>:`) | The parser only renames "Chat History with …" keys automatically when there are at least two of them that look alike, so an account with a single chat keeps the username. The parser documentation uses this exact path as its example of a variable-key path rule: `/user_data_tiktok.json/Direct Message/Direct Messages/ChatHistory/Chat History with *`. Adding that rule for TikTok in the admin should fix it, and saving a rule re-normalises stored uploads. The `feat/path_scrub` branch would not catch it, because its patterns match whole segments (emails, IDs, phone numbers) only. The path is already visible on the public site, so this is urgent |
| File paths anonymised when repeated values occur (`/your_facebook_activity/{*}/...`) | The parser collapses look-alike folders and renames variable keys to `{*}`. A "keep key" path rule can protect a folder, but the underlying need is to explain what `{*}` stands for (see 4.2) |
| Uploading a DDP with the earliest date is confusing | "New" and "Changed" are computed against uploads requested strictly earlier (`schemas/timeline.py`), so the earliest upload shows everything as new |
| Download options missing (ChatGPT via the privacy centre) | Request mode is a fixed choice of app, browser or Portability API (`ddps/models.py`) |
| CSV upload for Twitter missing | The parser handles CSV and X's `.js` files, so this is likely a platform setup or form option issue; it needs reproducing |
| Language matching of paths; language flag on data points | Language is recorded per upload, and translated keys are only suggested at registration; there is no per-data-point language |
| Account registration email refers to example.com | `django.contrib.sites` is enabled with `SITE_ID = 1`, but the site's domain is never set, so it keeps Django's default |

## Sources

- DDP Tracker repository, `dev` branch: https://github.com/Nico-AP/ddp-tracker
- DDP Tracker documentation: https://www.ddp-tracker.org/docs/
- Data Donation Lab, University of Zurich: https://datadonation.uzh.ch/en/
- Hackathon document (infrastructure track), version of 30 September 2026: https://docs.google.com/document/d/1OxUawA7hqIjOCjSmRn8rTSojv0jCSojuSXnBeLAvFRs/edit
- Pfiffner, N., Witlox, P. and Friemel, T. N. (2024). Data Donation Module: A web application for collecting and enriching data donations. *Computational Communication Research*, 6(2), 1–19. https://doi.org/10.5117/CCR2024.2.4.PFIF
