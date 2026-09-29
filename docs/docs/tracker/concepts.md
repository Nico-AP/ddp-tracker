# Definitions (technical reference)

!!! note "For developers"
    This page defines precisely how the DDP Tracker models what it learns from uploaded DDPs and
    what its statuses mean, with the parts of the code that implement them. Code, interface and
    tests follow these definitions; change them here first. For a plain-language description, see
    the [user guide](../index.md).

## Building blocks

| Term            | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Upload**      | One DDP as uploaded, with its platform, request date, request format and (optionally) account language. The file itself is parsed and deleted; only its schema document is kept. Its file name is stored anonymized (`ddps/names.py`): whitelisted words (formats, export terms, platforms) stay, other letters become `x`, digits `0`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **Location**    | A path (see the [parser spec](../ddp_parser/index.md#23-paths)) ever seen in a platform's registered uploads. It holds only identity (the path), its place in the tree, and curation: its annotation, "not a data point", example values.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Observation** | A location as it appears in one upload: kind, type, shape, format, stats. **Everything descriptive about a location is derived from its observations**, so any view can be restricted to a subset of uploads.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Annotation**  | A data point (e.g. "watched videos") and what is known about it: name, description, note, and whether it is personally identifiable information (PII). It has one or more locations: moved or renamed keys, keys named differently in exports of another language. A location belongs to at most one annotation. Example values are kept per location, since they can differ between them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Data point**  | A location that carries meaning of its own, and so is open for annotation: a **value**, a **list**, a **list's item** (`<item>`, path `…/[]`), or a **media** file. The item carries the meaning ("ID", "watched video"): its examples, format and representations; its fields (`VideoList[]/<item>/Date`) are data points of their own. List and item each get their own annotation; the list is annotated in its own step after the item, its name suggested from the item's ("List of …"). An item isn't *missing* from an upload whose list is present but empty. A parsed file whose content is a list (a JSON array, a CSV's rows) *is* that list. Objects only group keys (e.g. `profile`, `user`) unless they are a list's item, and other files, unmatched files, folders, zip containers and the root only describe where data lies: they are never annotated. A location is a data point in a view if any of its observations in the view is one. |

## Upload checks

To keep wrong or spam files out of the public schema, an upload only **counts** (is registered:
part of the explorer, reviews, "new" and "changed") once it passed these checks
(`ddp_tracker/ddps/checks.py`). Unlike "new" and "changed", they compare with the platform's
uploads **whatever their request date**: the duplicate check with all its uploads, the
similarity with all its counted uploads of the same root format.

- **Declared format.** The uploader says what the file is (ZIP archive, JSON file, CSV file). The
  form refuses a file whose extension or first bytes don't fit; after parsing, an upload whose
  parsed format differs from the declared one fails. This prevents accidental uploads of
  wrong files.
- **Duplicate.** The same file (SHA-256) as an upload of the platform that counts or waits for
  approval: kept, but never counted twice.
- **First of its kind.** The first upload of a platform and format has nothing to be compared
  with and defines what later ones are compared with: it **waits for approval by a staff account**.
- **Similarity.** The share of the upload's data points that the counted uploads of the same
  platform and format already know, at the same path or through a *moved*/*renamed* suggestion
  (so moved or translated exports still match). Below `DDP_SIMILARITY_THRESHOLD` (default 30 %),
  or with no data points at all, the upload is **unusual**: its uploader confirms it (it then
  waits for approval by a staff account) or discards it.

**Approval** is by staff (the *Approvals* page, or the upload's page), their own uploads
included. Approved uploads count; rejected ones don't.

**Inspecting a held upload.** An upload that doesn't count isn't registered, so it has no review.
To decide on it, its uploader and staff (nobody else: it may not be a DDP at all) can
**inspect** it (`ddp_tracker/ddps/inspection.py`): its files and data points, computed from its
schema document. Each data point is compared with what is already known about the platform, that
is, the counted uploads of the same platform and root format, whatever their request date. It is
**known** (at the same path), **matched** (a *moved*/*renamed* suggestion links it to a known
path) or **new**; **missing** are the known data points it has neither at their path nor matched.
The share of known and matched data points is the similarity above. The uploader also
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
- **How long.** Until `DDP_VALUES_RETENTION_DAYS` (default 3) are over, the uploader deletes
  them, or logs out (which deletes the key). `manage.py purge_upload_values` removes expired ones.
- **Shown** on the upload's review page (rows, side panel, annotation dialog). In the side panel,
  the uploader can **contribute values to the data point's examples** once it is annotated, as they are (not editable):
  only then do they become public.

Each example records where it came from (`schemas/examples.py`): **extracted** (contributed from
an uploader's file, never edited; curators can only keep or remove it) or **user input** (typed
in the examples form).

## How nodes are labelled

The explorer and review describe nodes in plain language; paths and the technical kinds and
types (shown in the node's facts) don't change.

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

**New**, **changed** and the **suggestions** compare an upload with the registered uploads of the
same platform **requested strictly earlier** (`schemas/timeline.py`, `schemas/services.py`):
request dates decide, never the order in which uploads were registered. Two uploads with the same
request date don't count as earlier than each other. **Missing** isn't date-based: it is about
the platform's annotations, whichever upload their locations came from, later-requested ones
included. The upload checks aren't date-based either (see *Upload checks*).

| Status         | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **New**        | No upload requested earlier has the path.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Changed**    | The location isn't new, and for at least one field (`kind`, `type`, `shape`, `format`) the upload's value appears in **no upload requested earlier**. Ignored as data-dependent noise: `null` in types, the shapes `mixed` and `empty`, and missing formats.                                                                                                                                                                                                                                                                                                                                                                                             |
| **Missing**    | An annotation none of whose locations appears in the upload: the platform removed the data point, or this account never used the feature. How often and until when it was seen before helps to tell which. An annotated path that a data point of the upload likely matches isn't missing: it appears once, as that data point's *likely matches …*.                                                                                                                                                                                                                                                                                                     |
| **Untriaged**  | A data point with no annotation that isn't marked "not a data point". Values, lists and objects all need a decision.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Suggestion** | For an unknown data point, a known path it may correspond to (`moved` or `renamed`, [parser spec §9.3](../ddp_parser/index.md#93-suggesting-correspondences)), and so that path's annotation. Computed against the uploads **requested earlier** (the same cut-off as *new*), merged on the fly; nothing aggregated is stored. Recomputed for the later uploads when an older export is registered afterwards, so registration order doesn't matter. Uploads of different root formats (a single JSON file vs. a zip) are separate references: their trees don't share a root, so each gives its own candidates, and a path any of them knows gets none. |

On the **review page** (`ddp_tracker/reviews`), the upload's data points are split into four
tabs, each data point in exactly one:

- **New**: never seen before (the status *new* above). Likely moves and renames are here too,
  with their suggestion.
- **Known**: earlier uploads had the path, and nothing about it changed.
- **Changed**: earlier uploads had the path, but a field is new (see *changed* above).
- **Missing**: annotated locations this upload doesn't have.

New and Known are paths of the data points (the annotated ones too, unless *Only to assign* is
on); next to the switch, how many rows in the tab are still **to assign** (untriaged). The paths
look as follows:

- **Files** come first: one collapsible block per file (data points that are files themselves,
  like a file whose content is a list or a media file, sit in their folder's block).
- **Groups** inside a file are the key chains that need no annotation themselves (plain
  objects), e.g. *Ads and data › Off TikTok Activity*, with how many rows in them are open.
- **One row per data point**, except that a **list and its item share one row** (`VideoList[]`):
  the item carries the meaning, so the row is annotated item first, then the list in its own
  step (its name prefilled *List of …*); the row is done once both are. The fields of the items are rows below it.
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

## Representations

A **representation** says what the entries of a list mean, in the terms of a shared vocabulary,
e.g. "user · view · video" for each item of a watch history, so platforms can be compared. It
belongs to one **location** (never to an annotation: a location can be represented before, or
without, being annotated), and a location can have several. Only a **list's item that is an
object** (`VideoList[]/<item>`, including the items of a file that is a list, such as a JSON
array or a CSV's rows) can have representations for now; this is decided from all of the
location's observations (its main type), and a representation it has is kept when later uploads
change that. Its terms (actor types, activity types, object types, metadata roles) are curated in
the database and can be extended. Relations point at a term's id; its slug is the stable name code
and seeds use to look it up, and is fixed once created; its name can be edited. A slot that
metadata links describe can't be emptied until those links are removed. Names needn't be unique.

| Term                | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Pattern**         | **Activity**: something happened, *actor · activity · object*, optionally *· target* (user · view · video; user · add · video · collection; other user · follow · person). Actor types: the **user** (the data donor), **other user** (another account, e.g. a follower), the **platform**. **Object**: something exists (profile). **Unmapped**: no confident mapping yet.                                                                                                           |
| **Location**        | The list's item the representation is about (one watched video). Set when it is created, never changed.                                                                                                                                                                                                                                                                                                                                                                               |
| **Metadata link**   | A data point **below** the location (any depth, not ignored) that *describes* the entry, with a **role** (when, duration, identifier, name …) and a **subject**: one of the slots the representation fills (`actor`, `activity`, `object`, `target`). E.g. TikTok's `Date` is *when* of the activity, its `Link` the *identifier* of the object; for an object representation everything describes the object. Unmapped representations fill no slot, so they have no metadata links. |
| **Suggested term**  | A term a signed-in user proposed (on the vocabulary page). Its suggester can use it right away; an admin approves it, and only then is it listed publicly and offered to others.                                                                                                                                                                                                                                                                                                      |

Curators add representations from the **Representations** section of the explorer's side panel and
the upload review, for a list's item: **"Add representation"** opens the representation dialog.
It has one section per slot the pattern shows, each with its term and its metadata rows (data
point, role; the section is the subject; "no confident mapping" has none), then the name and
description. The section lists a location's representations read-only; **"Edit"** (there and on
the representation's page) opens the same dialog to change anything, metadata included (its rows
replace the links), or to delete the representation. The representations page lists them all,
with their platform and location; a representation's page shows its metadata by subject and role.

## Suggestions and approval

**Only staff decide** what is curated; everyone else **suggests** (`ddp_tracker/proposals`). The
curated data (annotations, which annotation a location has, representations and their metadata)
only ever holds approved changes; a suggestion waits beside it as a *proposal*.

- **What is suggested:** annotating a location (link to an annotation, a new annotation, "not a
  data point", removing the assignment), editing an annotation, and representations (new, edited
  with their metadata, deleted). Suggestions can be corrections to what is
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

The platform page shows one **request format** at a time (the platform's most common first) and,
within it, one **root format**: a ZIP and a single file don't share a tree, so a second selector
appears when a request format has both. Filters narrow the uploads by request date range and
account language. Everything shown (paths, observed values and counts, when and how often they
were seen, the figures) comes from the matching uploads only; triage and suggestions aren't
filtered.

The tree looks like the review's (files, key chains, one row per data point, list and item
together); nodes that hold something but are never data points (an unparsed file, an object
always empty) are muted rows. It is alphabetical, ignoring case, so paths that differ only in
case (`TikTok Live`, `Tiktok Live`) sit side by side. A selector shows all data points, only
those **missing an annotation**, or only annotated ones **missing a representation** (linked to
none, neither as entity nor as metadata; for a list, its item's annotation counts); a list stays
while rows below it match.
