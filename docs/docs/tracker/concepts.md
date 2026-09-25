# DDP Tracker: concepts and definitions

How the web app models what it learns from uploaded DDPs, and what its statuses mean. Code, UI
and tests follow these definitions; change them here first.

## Building blocks

| Term            | Meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
|-----------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Upload**      | One DDP as uploaded, with its platform, request date and (optionally) account language. The file itself is parsed and deleted; only its schema document is kept.                                                                                                                                                                                                                                                                                                                  |
| **Location**    | A path (see the [parser spec](../ddp_parser/index.md#23-paths)) ever seen in a platform's registered uploads. It holds only identity (the path), its place in the tree, and curation: its annotation, "not a data point", example values.                                                                                                                                                                                                                                         |
| **Observation** | A location as it appears in one upload: kind, type, shape, format, stats. **Everything descriptive about a location is derived from its observations**, so any view can be restricted to a subset of uploads.                                                                                                                                                                                                                                                                     |
| **Annotation**  | A data point (e.g. "watched videos") and what is known about it: name, description, note. It has one or more locations: moved or renamed keys, keys named differently in exports of another language. A location belongs to at most one annotation. Example values are kept per location, since they can differ between them.                                                                                                                                                     |
| **Data point**  | A location that carries meaning of its own, and so is open for annotation: a **value**, a **list**, an **object that is the item of a list** (the repeated entity, `…/[]`), or a **media** file. Objects elsewhere only group keys (e.g. `profile`, `user`), and parsed files, unmatched files, folders, zip containers and the root only describe where data lies: they are never annotated. A location is a data point in a view if any of its observations in the view is one. |

## Statuses of an upload's locations

All comparisons are between an upload and the uploads of the same platform **requested strictly
earlier**: request dates decide, never the order in which uploads were registered. Two uploads
with the same request date don't count as earlier than each other.

| Status         | Definition                                                                                                                                                                                                                                                                                                                                                                                                                                           |
|----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **New**        | No upload requested earlier has the path.                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Changed**    | The location isn't new, and for at least one field (`kind`, `type`, `shape`, `format`) the upload's value appears in **no upload requested earlier**. Ignored as data-dependent noise: `null` in types, the shapes `mixed` and `empty`, and missing formats.                                                                                                                                                                                         |
| **Missing**    | An annotation none of whose locations appears in the upload: the platform removed the data point, or this account never used the feature. How often and until when it was seen before helps to tell which.                                                                                                                                                                                                                                           |
| **Untriaged**  | A data point with no annotation that isn't marked "not a data point". Values, lists and objects all need a decision.                                                                                                                                                                                                                                                                                                                                 |
| **Suggestion** | For an unknown data point, a known path it may correspond to (`moved` or `renamed`, [parser spec §9.3](../ddp_parser/index.md#93-suggesting-correspondences)), and so that path's annotation. Computed against the uploads **requested earlier** (the same cut-off as *new*), merged on the fly; nothing aggregated is stored. Recomputed for the later uploads when an older export is registered afterwards, so registration order doesn't matter. |

Example for **changed**, one location's `format`, uploads in order of request date:

| Requested | Format      | Changed?                          |
|-----------|-------------|-----------------------------------|
| 2025-03   | `%Y-%m-%d`  | – (new)                           |
| 2025-09   | `%Y-%m-%d`  | no                                |
| 2026-02   | `%d.%m.%Y`  | **yes**: no earlier upload had it |
| 2026-05   | `%Y-%m-%d`  | no: seen before                   |
| 2026-07   | `%d.%m.%Y`  | no: seen before                   |

## Filtering

The collected schema (platform page) can be restricted to the uploads matching a filter: request
date range, account languages, and how the DDP was uploaded (ZIP archive, single CSV/JSON file).
Everything shown (which paths exist, their observed values with counts, when and how often they
were seen, the counts at the top) is computed from the matching uploads only. Triage and
suggestions are not filtered: whether a path is known doesn't depend on the current view.

## Not yet

- Filters on the annotation list and annotation pages (they show all uploads for now).
- More filter dimensions, e.g. specific uploads or the parser version.
