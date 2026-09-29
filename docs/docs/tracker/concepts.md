# DDP Tracker: concepts and definitions

How the web app models what it learns from uploaded DDPs, and what its statuses mean. Code, UI
and tests follow these definitions; change them here first.

## Building blocks

| Term            | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Upload**      | One DDP as uploaded, with its platform, request date and (optionally) account language. The file itself is parsed and deleted; only its schema document is kept. Its file name is stored anonymized (`ddps/names.py`): whitelisted words (formats, export terms, platforms) stay, other letters become `x`, digits `0`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **Location**    | A path (see the [parser spec](../ddp_parser/index.md#23-paths)) ever seen in a platform's registered uploads. It holds only identity (the path), its place in the tree, and curation: its annotation, "not a data point", example values.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Observation** | A location as it appears in one upload: kind, type, shape, format, stats. **Everything descriptive about a location is derived from its observations**, so any view can be restricted to a subset of uploads.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Annotation**  | A data point (e.g. "watched videos") and what is known about it: name, description, note, and whether it is personally identifiable information (PII). It has one or more locations: moved or renamed keys, keys named differently in exports of another language. A location belongs to at most one annotation. Example values are kept per location, since they can differ between them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Data point**  | A location that carries meaning of its own, and so is open for annotation: a **value**, a **list**, a **list's item** (`<item>`, path `…/[]`), or a **media** file. The item carries the meaning ("ID", "watched video"): its examples, format and representations; its fields (`VideoList[]/<item>/Date`) are data points of their own. List and item each get their own annotation; the list is annotated in its own step after the item, its name suggested from the item's ("List of …"). An item isn't *missing* from an upload whose list is present but empty. A parsed file whose content is a list (a JSON array, a CSV's rows) *is* that list. Objects only group keys (e.g. `profile`, `user`) unless they are a list's item, and other files, unmatched files, folders, zip containers and the root only describe where data lies: they are never annotated. A location is a data point in a view if any of its observations in the view is one. |

## Upload checks

To keep wrong or spam files out of the public schema, an upload only **counts** (is registered:
part of the explorer, reviews, "new" and "changed") once it passed these checks
(`ddp_tracker/ddps/checks.py`):

- **Declared format.** The uploader says what the file is (ZIP archive, JSON file, CSV file). The
  form refuses a file whose extension or first bytes don't fit; after parsing, an upload whose
  parsed format differs from the declared one fails.
- **Duplicate.** The same file (SHA-256) as an upload of the platform that counts or waits for
  approval: kept, but never counted twice.
- **First of its kind.** The first upload of a platform and format has nothing to be compared
  with and defines what later ones are compared with: it **waits for approval**.
- **Similarity.** The share of the upload's data points that the counted uploads of the same
  platform and format already know, at the same path or through a *moved*/*renamed* suggestion
  (so moved or translated exports still match). Below `DDP_SIMILARITY_THRESHOLD` (default 30 %),
  or with no data points at all, the upload is **unusual**: its uploader confirms it (it then
  waits for approval) or discards it.

**Approval** is by staff (the *Approvals* page, or the upload's page), their own uploads
included. Approved uploads count; rejected ones don't.

**Inspecting a held upload.** An upload that doesn't count isn't registered, so it has no review.
To decide on it, its uploader and staff (nobody else: it may not be a DDP at all) can
**inspect** it (`ddp_tracker/ddps/inspection.py`): its files and data points, computed from its
schema document, each data point compared with the counted uploads of the same platform and
format as **known** (at the same path), **matched** (a *moved*/*renamed* suggestion links it to a
known path) or **new**; and the **missing** known data points it has neither at their path nor
matched. The share of known and matched data points is the similarity above. The uploader also
sees their own values. Inspecting registers nothing.

## The uploader's values

Everything public is derived from the structure only. To make annotating easier, each upload also
keeps a few real values per data point (`DDP_VALUES_PER_POINT`, default 5) **for its uploader
alone** (`ddp_tracker/ddps/values.py`):

- **What.** The parser's samples: the first distinct values of each data point. Email addresses
  are masked (`anna@example.com` → `axxx@xxxxxxx.xxx`), also inside texts. They are taken out of
  the upload's schema document: no observation, explorer or review ever holds them.
- **Where.** Encrypted with the upload's public key. The private key is only in a signed cookie
  in the browser the DDP was uploaded from, never in the session or the database: the database
  alone doesn't reveal them.
- **Who.** Only the uploader, logged in, in that browser; not other curators and not staff (they
  aren't in the admin either).
- **How long.** Until `DDP_VALUES_RETENTION_DAYS` (default 30) are over, the uploader deletes
  them, or logs out (which deletes the key). `manage.py purge_upload_values` removes expired ones.
- **Shown** on the upload's review page (rows, side panel, annotation dialog). In the side panel,
  the uploader can **contribute values to the data point's examples** once it is annotated, as they are (not editable):
  only then do they become public.

Each example records where it came from (`schemas/examples.py`): **extracted** (contributed from
an uploader's file, never edited; curators can only keep or remove it) or **user input** (typed
in the examples form).

## How nodes are labelled

The explorer and review describe nodes in plain language; paths and the technical kinds and
types (shown on hover and in the node's facts) don't change.

| Node                               | Label                                                                                                                                     |
|------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| a list                             | **list of objects**, **list of integers**, **list of objects or texts** (what its items are)                                              |
| a list never seen with items       | **list (always empty so far)**; **empty list** when the view covers one upload (e.g. a review)                                            |
| a list's item (`…/[]`)             | named **`<item>`**, with its type (e.g. object, integer); a list's name ends in `[]` (`VideoList[]`)                                      |
| an object that only groups keys    | **group of keys**; **group of keys (always empty so far)** if it never had keys (e.g. `{"GroupChat": {}}`), **(empty)** within one upload |
| a value                            | **text**, **integer**, **number**, **true/false**; **(or empty)** if it can be `null`                                                     |
| a parsed file                      | **file: list of objects**, **file: group of keys**                                                                                        |
| folder, zip, media, unmatched file | **folder**, **archive**, **media file**, **unreadable file**                                                                              |

Below a node's path, the side panel can show where it sits **as JSON**: the keys leading to it,
then, one key per line, the node itself if it is an object or a list (a list's item opened), else
its parent with the node's siblings. Values are placeholders: the type and, when it says
something, the shape (`<text>`, `<integer>`, `<text · datetime>`; the parser's fallback shapes
`plain` and `text` are left out). Objects and lists further away are abbreviated (`{…}`, `[…]`).
It reflects the uploads in view (the filter), not any single file.

## Statuses of an upload's locations

All comparisons are between an upload and the uploads of the same platform **requested strictly
earlier**: request dates decide, never the order in which uploads were registered. Two uploads
with the same request date don't count as earlier than each other.

| Status         | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **New**        | No upload requested earlier has the path.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Changed**    | The location isn't new, and for at least one field (`kind`, `type`, `shape`, `format`) the upload's value appears in **no upload requested earlier**. Ignored as data-dependent noise: `null` in types, the shapes `mixed` and `empty`, and missing formats.                                                                                                                                                                                                                                                                                                                                                                                             |
| **Missing**    | An annotation none of whose locations appears in the upload: the platform removed the data point, or this account never used the feature. How often and until when it was seen before helps to tell which. An annotated path that a data point of the upload likely matches isn't missing: it appears once, as that data point's *likely matches …*.                                                                                                                                                                                                                                                                                                     |
| **Untriaged**  | A data point with no annotation that isn't marked "not a data point". Values, lists and objects all need a decision.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Suggestion** | For an unknown data point, a known path it may correspond to (`moved` or `renamed`, [parser spec §9.3](../ddp_parser/index.md#93-suggesting-correspondences)), and so that path's annotation. Computed against the uploads **requested earlier** (the same cut-off as *new*), merged on the fly; nothing aggregated is stored. Recomputed for the later uploads when an older export is registered afterwards, so registration order doesn't matter. Uploads of different root formats (a single JSON file vs. a zip) are separate references: their trees don't share a root, so each gives its own candidates, and a path any of them knows gets none. |

On the **review page** (`ddp_tracker/reviews`), the upload's data points form a tree (the
annotated ones too, unless *Hide annotated* is on; the counts are always the open ones):

- **Files** come first: one collapsible block per file (data points that are files themselves,
  like a file whose content is a list or a media file, sit in their folder's block). Only the
  first file with something to assign, and its first such group, start expanded.
- **Groups** inside a file are the key chains that need no annotation themselves (plain
  objects), e.g. *Ads and data › Off TikTok Activity*, with how many rows in them are open. The
  data points directly in the file have no group heading.
- **One row per data point**, except that a **list and its item share one row** (`VideoList[]`):
  the item carries the meaning, so the row is annotated item first, then the list in its own
  step (its name prefilled *List of …*); the row is done once both are. The fields of the items are rows below it; a
  decided list stays there while any of them is open.
- Each row shows the type, a suggestion (*Moved? …* / *Renamed? …*: the earlier path it
  **likely matches**; nothing is claimed about why the path differs), a preview (the uploader's
  own values, else the number of items or the format) and whether it is decided.
- The **annotation dialog** lies over the tree, so the side panel stays readable and usable:
  a new annotation (name, description, note, PII), or a search through the existing ones to link.
- The **side panel** is for annotating: why the data point is here (**new**: no earlier upload
  has the path; **likely moved/renamed**; **seen before**: earlier uploads had it, but it was
  never annotated), the suggestion as the main action, the values found in the file (uploader
  only), and, **once it is annotated**, contributing those values to the examples and linking
  representations. The technical details are collapsed.

*Changed* rows say, per field, what earlier uploads had and what this one has.

Example for **changed**, one location's `format`, uploads in order of request date:

| Requested | Format      | Changed?                          |
|-----------|-------------|-----------------------------------|
| 2025-03   | `%Y-%m-%d`  | – (new)                           |
| 2025-09   | `%Y-%m-%d`  | no                                |
| 2026-02   | `%d.%m.%Y`  | **yes**: no earlier upload had it |
| 2026-05   | `%Y-%m-%d`  | no: seen before                   |
| 2026-07   | `%d.%m.%Y`  | no: seen before                   |

## Representations (cross-platform)

A **representation** describes a concept independently of any platform, so annotations of different
platforms can be compared. Its terms (actor types, activity types, object types, metadata roles)
are curated in the database and can be extended. Relations point at a term's id; its slug is the
stable name code and seeds use to look it up, and is fixed once created; its name can be edited. A slot that metadata links describe can't be emptied until those links are removed.

| Term                | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Pattern**         | **Activity**: something happened, *actor · activity · object*, optionally *· target* (user · view · video; user · add · video · collection; other user · follow · person). Actor types: the **user** (the data donor), **other user** (another account, e.g. a follower), the **platform**. **Object**: something exists (profile). **Unmapped**: no confident mapping yet.                                                                                                                       |
| **Representing**    | Annotations that *are* the concept: the entity node itself: by default a list's `<item>` (one watched video), on any number of platforms. Can be empty: plain objects (`profile`) are no data points, so a "Profile" representation only has metadata links; a link's platform is its annotation's.                                                                                                                                                                                               |
| **Metadata link**   | An annotation that *describes* the concept, with a **role** (when, duration, identifier, name …) and a **subject**: one of the slots the representation fills (`actor`, `activity`, `object`, `target`). E.g. TikTok's `Date` is *when* of the activity, its `Link` the *identifier* of the object, a follower's username the *name* of the actor; for an object representation (profile) everything describes the object. Unmapped representations fill no slot, so they have no metadata links. |
| **Suggested term**  | A term a signed-in user proposed (on the vocabulary page). Its suggester can use it right away; an admin approves it, and only then is it listed publicly and offered to others.                                                                                                                                                                                                                                                                                                                  |

Curators assign annotations and link representations through **"Add annotation"** and **"Add
representation"** (a dialog), from the explorer's side panel, the upload review and the annotation's
page: **select an existing** one (something happened or something exists; the data point *is* it,
or *describes* one of its slots), or **add a new** one, the data point as its entity, with any
number of metadata rows (subject, role, annotation; not for "no confident mapping"). The
representation's page shows the result across platforms: what represents it, and a table of who
records what (subject and role × platform).

## Suggestions and approval

**Only staff decide** what is curated; everyone else **suggests** (`ddp_tracker/proposals`). The
curated data (annotations, which annotation a location has, representations and their links)
only ever holds approved changes; a suggestion waits beside it as a *proposal*.

- **What is suggested:** annotating a location (link to an annotation, a new annotation, "not a
  data point", removing the assignment), editing an annotation, and representations (new, edited,
  linked as the entity or as metadata, links removed). Suggestions can be corrections to what is
  already annotated. Example values are not suggested: they change directly.
- **Staff's own changes apply directly**; for everyone else the same buttons read "Suggest …".
- **Deciding:** staff go through two queues, annotations (by platform) and representations, one
  suggestion at a time. **Accepting** applies it (as the proposer's change) and **supersedes** the
  other open suggestions for the same target; **rejecting** records a reason for the proposer. A
  suggestion made on a state that has changed since is **stale**: staff confirm before accepting.
  A representation using vocabulary terms that aren't approved yet waits for those.
- **Statuses:** open, accepted, rejected, withdrawn (by the proposer, or replaced by their newer
  one for the same target), superseded. Proposals stay as the history of who suggested and
  decided what.
- **No chaining:** a suggestion refers to approved annotations and representations only (a list's
  "List of …" waits until its item's annotation is approved).
- **Pending:** open suggestions are visible to everyone. A data point with one shows "N
  suggestions"; in the review it still counts as open, with its own (pending) dot. Panels and the
  annotation and representation pages list the open suggestions; "My suggestions" shows a user's
  own, with how they were decided.

## Filtering

The collected schema (platform page) shows **one upload format at a time** (ZIP archive, single
CSV/JSON file): a single file and a zip don't share a tree. It opens on the platform's most
common format; the others are one click away. Within it, a filter restricts the uploads by
request date range and account languages. The tree is alphabetical, ignoring case (positions in
a file differ between uploads; the review keeps its one upload's file order), so paths that differ
only in case, like TikTok's `TikTok Live` and `Tiktok Live`, are separate locations shown right
next to each other. The tree looks like the review's (files, key chains,
one row per data point, list and item together), with nodes that are never data points but hold
something (an unparsed file, an object always seen empty) as muted rows, and a side panel that
shows everything known about a location. A selector shows all data points, only
those **missing an annotation**, or only annotated ones **missing a representation** (their
annotation, for a list its item's, is linked to no representation, neither as the entity nor as
metadata); a list stays shown while rows below it match. Everything shown (which paths exist, their observed values with counts, when and how often they
were seen, the counts at the top) is computed from the matching uploads only. Triage and
suggestions are not filtered: whether a path is known doesn't depend on the current view.

## Not yet

- Filters on the annotation list and annotation pages (they show all uploads for now).
- More filter dimensions, e.g. specific uploads or the parser version.
