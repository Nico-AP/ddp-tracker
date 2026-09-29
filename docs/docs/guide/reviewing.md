# Reviewing an upload

Each upload that counts has a **review**: its data points, compared with what is known about the
platform. Whether a data point is new, known or changed is worked out against the uploads of the
platform that were **requested earlier**. The request date decides, not the date of uploading,
so an older DDP uploaded late still slots in at the right place.

## The four tabs

Every data point of the upload is in exactly one of the first three tabs:

| Tab          | What it holds                                                                                                                                                                                                                                                 |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **New**      | data points no earlier upload had. Some were probably only moved or renamed: they say so ("Moved? …", "Renamed? …") and suggest the earlier field's annotation.                                                                                               |
| **Known**    | data points earlier uploads had, unchanged.                                                                                                                                                                                                                   |
| **Changed**  | data points earlier uploads had, but something about them is new: their kind, type, or format (for example dates written differently). Each shows what earlier uploads had and what this one has.                                                             |
| **Missing**  | annotated data points that this upload doesn't have, from any of the platform's uploads (also ones requested later): the platform may have removed them, or this account never used the feature. How often and until when they were seen helps to tell which. |

A data point only counts as changed if **no** earlier upload had the new value. If a platform
switches a date format back and forth, only the first switch is a change:

| Requested | Date format   | Changed?                          |
|-----------|---------------|-----------------------------------|
| 2025-03   | `2025-03-01`  | – (new)                           |
| 2025-09   | `2025-09-01`  | no                                |
| 2026-02   | `01.02.2026`  | **yes**: no earlier upload had it |
| 2026-05   | `2026-05-01`  | no: seen before                   |
| 2026-07   | `01.07.2026`  | no: seen before                   |

## Working through New and Known

New and Known show their data points as a tree, like the [explorer](exploring.md): one block per
file, fields grouped under headings, lists with their entries' fields below them.

- **Only to assign** hides the data points that are already annotated. Next to it, how many are
  still **to assign** in this tab; the progress bar shows the whole upload.
- A dot at the end of each row shows its state: to assign, suggested (waiting for staff), or
  done.
- A list whose entries gained a new field appears in New as a faded heading for that field,
  even though the list itself is known.
- Use <kbd>↑</kbd> and <kbd>↓</kbd> to move between rows and <kbd>Enter</kbd> to annotate.

Select a row to open the side panel: why the data point is here (new, likely moved or renamed,
or seen before but never annotated), the suggestion as the main action, and the values found in
your file (only you see those, see [Privacy](privacy.md)). Annotating is described in
[Annotating](annotating.md).
