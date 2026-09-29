# Parser: schema format (technical reference)

!!! note "For developers and researchers"
    This page describes the format of the **schema document** the DDP Parser produces from a DDP -
    in other words what the DDP Tracker keeps of every upload.
    Generally, you only need it if you work with these documents (`packages/ddp-parser`)
    or to interpret certain information included in the schema explorer.
    To use the DDP Tracker, see the [user guide](../index.md).

The parser takes a ZIP archive or a single file and describes its structure as a tree of
**nodes**: one for every folder, file, key and value position. Each node records what kind of
thing it is and what its values looked like, never the values themselves (unless samples are
explicitly requested, see [Samples](#samples)).

## Nodes

### Common Fields

Every node has:

| Key     | Required | Description                                                                                                   |
|---------|----------|---------------------------------------------------------------------------------------------------------------|
| `kind`  | yes      | What the node is: `container`, `folder`, `file`, `media`, `unmatched`, `data`.                                |
| `name`  | yes      | File/folder name, or the JSON key / CSV column. `null` for array items.                                       |
| `path`  | yes      | Unique location in the tree, as a JSON Pointer string (see [Paths](#23-paths)). Used for diffing schemas.     |

### Kinds

| Kind        | Represents                                                                                              | Holds its content in       |
|-------------|---------------------------------------------------------------------------------------------------------|----------------------------|
| `container` | A zip archive (top level or nested)                                                                     | `children` (list of nodes) |
| `folder`    | A directory inside a container, or collapsed look-alike ones (`folders`, [§3.5](#35-collapsed-folders)) | `children` (list of nodes) |
| `file`      | A file that was **successfully parsed** (JSON, CSV, …)                                                  | `properties` / `items`     |
| `media`     | An image / video / audio file (not parsed, metadata only)                                               | –                          |
| `unmatched` | Any other file, or a file whose parse failed                                                            | –                          |
| `data`      | A value inside parsed content: scalar, object or array                                                  | `properties` / `items`     |

Filesystem-like kinds (`container`, `folder`, `file`, `media`, `unmatched`) all
carry the **file metadata** from [§4](#4-file-metadata). A `file` node also
describes its parsed content **inline**: it carries the same schema fields as a
`data` node (`type`, `stats`, `properties` / `items`, …, see [§3](#3-data-nodes)),
so a file and the top-level value inside it are one node.

### 2.3 Paths

A path identifies a **schema node**, not a single value: it says where in the
schema tree the node sits. It is a string in
[JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901) form:

- The root node has the empty path `""`. The root container's own file name is
  not part of any path (it is in `source.name`). When the input is a single
  file rather than a zip, that file is the root node.
- Every folder or file entry, and every object key / CSV column below it, adds
  `/` + its name. Inside names, `~` is written as `~0` and `/` as `~1`
  (in that order), exactly as in JSON Pointer.
- `/[]` is the one **reserved segment**: the unified item node of an array
  (all items at once).
- A group of merged files (see [Unification](#34-unification)) appears under
  its name pattern, e.g. `/message_{n}.json`.
- Collapsed look-alike folders (see [Collapsed folders](#35-collapsed-folders))
  appear as `/{*}`, e.g. `/messages/inbox/{*}/message_{n}.json`.

Folder entries and object keys need no separate markers: a folder or zip only
ever contains entries, and a parsed file or object only ever contains keys, so
the node's `kind` already tells them apart.

**Example** — the `sender_name` field of the messages in one chat file:

```
/messages/inbox/chat_1/message_1.json/messages/[]/sender_name
```

**Comparing schema documents**

Two nodes from different schema documents describe the same place if their
`path` strings are equal. This makes it possible to diff the same platform's
export before and after a format change. Paths are stable only as long as names
are: a renamed key or file shows up as one removed and one added node, which is
exactly what a diff should report.

**Known limitations**, accepted to keep paths simple:

- An object key literally named `[]` produces the same path as an array's item
  node. The parser records a `reserved_name` warning when it meets one.
- A file literally named like a group pattern (`message_{n}.json`) next to a
  group with that pattern, or a folder literally named `{*}` next to collapsed
  folders, would share its path. Real exports do not do this.

---

## 3. `data` nodes

### 3.1 Fields

```json
{
  "kind": "data",
  "name": "timestamp",
  "path": "/posts.json/[]/timestamp",
  "type": "string",
  "shape": "datetime",
  "format": "%Y-%m-%d %H:%M:%S",
  "length": { "min": 19, "max": 19 },
  "stats": { "count": 1204, "present": 1204, "null": 0 },
  "shapes": { "datetime": 1204 }
}
```

| Key          | Applies to          | Description                                                                               |
|--------------|---------------------|-------------------------------------------------------------------------------------------|
| `type`       | all                 | A type name, or a list of type names if values differ (see [Unions](#34-unification)).    |
| `shape`      | scalars             | Dominant semantic shape of the values (see [§3.3](#33-shapes)), or `mixed`.               |
| `shapes`     | scalars             | Count per detected shape. Shows exactly how "clean" a shape is.                           |
| `format`     | some shapes         | Further detail for the shape (see [§3.3](#33-shapes)).                                    |
| `length`     | `string`, `array`   | `{min, max}` of string length in characters, or of array item count.                      |
| `range`      | `integer`, `number` | `{min, max}` of observed values. Omitted unless samples are enabled (can be identifying). |
| `properties` | `object`            | Map of key name → child `data` node.                                                      |
| `items`      | `array`             | **One** `data` node that describes all items, unified.                                    |
| `stats`      | all                 | Observation counts (see below).                                                           |
| `samples`    | scalars             | Opt-in only (see [Samples](#samples)).                                                    |

**`stats`**

| Key       | Description                                                                                         |
|-----------|-----------------------------------------------------------------------------------------------------|
| `count`   | How many parent objects were inspected at this position (the denominator).                          |
| `present` | How many of those actually contained this key. `present < count` means the key is **optional**.     |
| `null`    | How many present values were JSON `null`. An empty CSV cell is an empty string, not `null`.         |

This separates three cases that are easy to conflate: key **missing**
(`count − present`), value **null** (`null`), value **empty string**
(`shapes.empty`).

### 3.2 Types

| Type      | Description                                                                                                                                          |
|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| `string`  | A sequence of zero or more Unicode characters.                                                                                                       |
| `integer` | A number literal without fraction or exponent (`1`, `-7`, `34231432142134`). Parsed with arbitrary precision; `1.0` is a `number`, not an `integer`. |
| `number`  | A number literal with a fraction or exponent (`1.0`, `234.334`, `1e5`).                                                                              |
| `boolean` | `true` or `false`.                                                                                                                                   |
| `null`    | JSON `null`.                                                                                                                                         |
| `object`  | A key/value map. Children in `properties`.                                                                                                           |
| `array`   | An ordered list. Unified item schema in `items`.                                                                                                     |

CSV cells are always strings on disk. The parser always infers types from them:

| Cell                                               | Becomes                 |
|----------------------------------------------------|-------------------------|
| Whole number without leading zeros (`42`, `-7`)    | `integer`               |
| Number with fraction or exponent (`3.14`, `1e5`)   | `number`                |
| `true` / `false` (any case)                        | `boolean`               |
| Anything else, including `007`, `+41 44…`, `""`    | `string` (unchanged)    |

Leading zeros stay strings because they carry meaning (postal codes, phone
numbers, IDs). An empty cell is the empty string, never `null`.

The first row of a CSV file is always read as the header (column names). Blank
names become `column_<n>` (1-based position) and repeated names get `_2`, `_3`, …
so no column overwrites another. A row with fewer cells than the header simply
lacks the missing keys (they show up as optional); extra cells are named
`column_<n>`. Blank lines are skipped.

### 3.3 Shapes

A shape is a semantic label detected on top of the type. Detection runs in the
order listed; **the first match wins**, so specific shapes are checked before
generic ones.

**For `string`**

| Order | Shape            | Matches                                             | `format`                                     |
|-------|------------------|-----------------------------------------------------|----------------------------------------------|
| 1     | `empty`          | `""` or whitespace only                             | –                                            |
| 2     | `uuid`           | 8-4-4-4-12 hex UUID                                 | –                                            |
| 3     | `email`          | An email address                                    | –                                            |
| 4     | `url`            | An absolute URL with a scheme (`http`, `https`, …)  | –                                            |
| 5     | `datetime`       | Date and time of day                                | strftime pattern, e.g. `%Y-%m-%dT%H:%M:%S%z` |
| 6     | `date`           | Date only                                           | strftime pattern, e.g. `%Y-%m-%d`            |
| 7     | `time`           | Time of day only                                    | strftime pattern, e.g. `%H:%M`               |
| 8     | `unix_timestamp` | Digits only, in the plausible range (see below)     | `s`, `ms` or `us`                            |
| 9     | `numeric`        | A number written as a string (`"42"`, `"3.14"`)     | –                                            |
| 10    | `alpha`          | Letters only, no whitespace (`"DE"`, `"active"`)    | –                                            |
| 11    | `alphanumeric`   | Letters and digits only, no whitespace (IDs, codes) | –                                            |
| 12    | `text`           | Anything else                                       | –                                            |

**For `integer` / `number`**

| Shape            | Matches                                         | `format`          |
|------------------|-------------------------------------------------|-------------------|
| `unix_timestamp` | Value in the plausible range (see below)        | `s`, `ms` or `us` |
| `plain`          | Anything else                                   | –                 |

**Detection rules**

- **Unix timestamps** match only between **1990-01-01 and 2100-01-01** in the
  given unit (seconds, milliseconds or microseconds; the ranges do not
  overlap). Values under a key named `id`, ending in `_id` or in `Id`
  (`userId`) never get the shape: IDs are the most common in-range numbers that
  are not timestamps. Other in-range values do; the `shapes` counts show when a
  node is only partly timestamp-like.
- **Ambiguous dates** (`01/02/2026`): the parser picks the pattern under which
  **all** values in the node parse. If both `%d/%m/%Y` and `%m/%d/%Y` still
  fit, the node gets no `format`, a `formats` count per candidate and a warning
  `ambiguous_date_order`.
- **Timezones**: `format` records the offset if present (`%z`). A trailing `Z`
  is recorded as the literal `Z` in the pattern. Fractional seconds are
  recorded as `%<n>f` with their digit count, e.g. `%Y-%m-%dT%H:%M:%S.%3fZ`
  for milliseconds. This is the only non-standard token: tools replace it with
  `%f` (which accepts 1–6 digits) before parsing with `strptime`.

### 3.4 Unification

Arrays are described by one `items` node, and a file seen many times (e.g.
`message_1.json` … `message_40.json`) can be merged into one schema. Merging
two nodes A and B follows these rules:

| Aspect       | Rule                                                                                                                                                    |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| `type`       | Equal → kept. Different → union list, sorted, e.g. `["null", "string"]`. `integer` + `number` → `number`.                                               |
| `stats`      | Summed field by field.                                                                                                                                  |
| `shapes`     | Counts summed.                                                                                                                                          |
| `shape`      | The shape covering ≥ `shape_threshold` (default 95 %) of non-empty values, otherwise `mixed`.                                                           |
| `format`     | Kept if equal; if different, it is omitted and the node gets `formats` (a count per format).                                                            |
| `length`     | `min` of mins, `max` of maxes.                                                                                                                          |
| `properties` | Union of keys. A key missing on one side keeps `count` from both sides but `present` only from the side that has it — that is how optional keys appear. |
| `items`      | Unified recursively.                                                                                                                                    |

Merging files is controlled by a **grouping rule**: files in the same folder
whose names differ only in their numbers (`message_1.json`, `message_2.json`)
are grouped. Every run of digits in the name becomes `{n}`, and files with the
same resulting pattern form a group once there are at least two of them (zips
are never grouped). The group is written once with the name pattern
`message_{n}.json` and
`files` = number of files merged. The group's `stats.count` counts the merged
top-level values (one per file), like any other `stats`.

If some files of a group cannot be read (parse error, over a size limit), they
are left out of the group and its `files` count, and a `group_member_failed`
warning names how many and why. They get no node of their own: their names
would clash with the group's other files. If none can be read, the group
becomes one `unmatched` node.

### Samples

With `options.samples = true`, scalar nodes get:

```json
"samples": { "values": ["…", "…"], "redacted": true }
```

- at most `options.max_samples` (default 3) distinct values per node
- the shapes in `options.masked_shapes` (default `email`, `url`, `text`,
  `alphanumeric`, `uuid`) are **redacted**:
  the first character is kept, then letters become `x`, digits `0`, and all
  other characters stay, so the shape remains visible
  (`anna@example.com` → `axxx@xxxxxxx.xxx`)
- `range` on numbers is only emitted when samples are on

### 3.5 Collapsed folders

Many exports hold one folder per conversation, album or period, named after a
person, a free-text title or a date (`messages/inbox/johndoe_1234/`,
`janedoe_5678/`, …). Kept as they are, these names put personal data into paths,
and exports of different users (or of one user over time) never share paths
below them. Such **look-alike sibling folders are collapsed** into one folder:

- Its path segment is `{*}` (`/messages/inbox/{*}`), the same in every export.
- Its `name` is a **mask** of the original names: letters become `x`, digits
  `0`, every other character `s`, and runs of the same character are merged, so
  `johndoe_1234` and `annasmith_98765` both give `xs0` (the most common mask
  wins if they differ). The mask shows what the names looked like without
  revealing them; it is not part of the path.
- `folders` counts how many folders were collapsed.
- Their contents are merged: files from all of them are grouped together
  ([§3.4](#34-unification)), and same-named subfolders merge recursively. So
  `message_1.json` of every conversation ends up in one
  `/messages/inbox/{*}/message_{n}.json` node.

```json
{"kind": "folder", "name": "xs0", "path": "/messages/inbox/{*}", "folders": 214, "children": ["…"]}
```

**When folders collapse.** Checked top-down for every folder's subfolders:

1. **Rules first.** `options.collapse_folders` and `options.keep_folders` list
   folder paths whose subfolders are always / never collapsed; `*` matches any
   one path segment (`/messages/*`). They let a platform-specific layer force
   or prevent a collapse. A forced collapse applies even to a single subfolder,
   so its name is masked too.
2. **Otherwise a heuristic.** The folder contains only subfolders (at least
   two), and they look alike inside: taking each subfolder's child names (with
   every run of digits as `{n}`), the names shared by *more than half* of the
   subfolders make up, on average, at least half of each subfolder's names.
   Conversation folders all share `message_{n}.json`; category folders such as
   `ads/` and `posts/` share nothing, so they stay as they are.

---

## 4. File metadata

### 4.1 Common metadata

Kinds `container`, `folder`, `file`, `media` and `unmatched` carry:

| Key            | Description                                                                                                                        |
|----------------|------------------------------------------------------------------------------------------------------------------------------------|
| `size_bytes`   | Uncompressed size in **bytes** (integer). Not set on folders.                                                                      |
| `modified`     | Last-modified time **as stored**, in ISO 8601 **without offset** (zip stores local time with no timezone and 2-second resolution). |
| `ext`          | Lower-cased extension including the dot (`.jpg`).                                                                                  |
| `mime`         | Detected MIME type.                                                                                                                |
| `mime_source`  | `magic` (from file content) or `extension` (fallback). Extensions in exports are often wrong.                                      |

Fields that are unknown are left out: the top-level input has no `modified`
(a zip only stores timestamps for its entries), a folder has one only when the
zip has an explicit entry for it, and a file without an extension has no `ext`.
For a group of files ([§3.4](#34-unification)), `size_bytes` is the total of
its files and `modified` the newest.

**`magic` vs `extension`.** Many binary formats begin with a fixed byte
sequence, a *file signature* or "magic number", e.g. `89 50 4E 47` (`‰PNG`) for
PNG, `FF D8 FF` for JPEG, `50 4B 03 04` (`PK`) for zip. The parser reads the
first bytes of each file and looks them up in a table of known signatures. A
match gives `mime_source: magic`, which describes what the file actually is, even
if it has no extension or the wrong one (e.g. a JPEG saved as `photo.png`).
Only when no signature matches does the MIME type come from the extension
(`mime_source: extension`). Plain-text formats such as JSON and CSV have no
signature, so they almost always get `extension`, as in the examples below.

`unmatched` nodes additionally carry `reason`: `unsupported_type`,
`parse_error`, `too_large` or `ignored`, and for `parse_error` a short
`error` message.

### 4.2 Parser details

`file` nodes additionally carry what was needed to read them, followed by the
schema fields of their parsed content (as in [§3.1](#31-fields)):

```json
{
  "kind": "file",
  "name": "posts.csv",
  "path": "/posts.csv",
  "size_bytes": 20482,
  "modified": "2026-08-01T10:12:04",
  "ext": ".csv",
  "mime": "text/csv",
  "mime_source": "extension",
  "encoding": "utf-8-sig",
  "parser": "csv",
  "csv": {
    "delimiter": ";",
    "quotechar": "\""
  },
  "type": "array",
  "length": { "min": 1204, "max": 1204 },
  "stats": { "count": 1, "present": 1, "null": 0 },
  "items": { "kind": "data", "name": null, "path": "/posts.csv/[]", "…": "…" }
}
```

| Key        | Description                                                                              |
|------------|------------------------------------------------------------------------------------------|
| `encoding` | Detected text encoding (`utf-8`, `utf-8-sig` for BOM, `utf-16-le`, `cp1252`, …).         |
| `parser`   | Which parser read it (see [§6](#6-supported-file-types)).                                |
| `csv`      | CSV dialect. CSV content is an array of objects, one per row; `length` is the row count. |
| `wrapper`  | For `js-json`: the prefix that was stripped, e.g. `window.YTD.tweets.part0 =`.           |
| `files`    | For a group of merged files (see [§3.4](#34-unification)): how many files were merged.   |

---

## 5. Zip handling

- **Nested zips** (entries named `*.zip`) become `container` nodes, up to
  `options.max_depth` (default 3). Deeper ones become `unmatched` with
  `reason: too_large`. Files that merely share the zip signature (`.docx`,
  `.jar`, `.epub`, …) are not opened.
- **Safety limits**, all configurable and recorded in `options`. They apply to
  what the parser reads (files it parses and nested zips); media files are only
  ever read for their first few bytes.

  | Option           | Default | Effect                                                            |
  |------------------|---------|-------------------------------------------------------------------|
  | `max_entry_size` | 256 MiB | A larger entry becomes `unmatched` with `reason: too_large`.      |
  | `max_total_size` | 4 GiB   | Once reached, further entries become `too_large` too.             |
  | `max_entries`    | 200 000 | Per container; further entries are skipped, with a warning.       |

  Limits use each entry's *declared* size. That is enough against zip bombs:
  reading never returns more than the declared size (a forged size fails the
  checksum and becomes a `parse_error`), so there is no separate
  compression-ratio check.
- **Path traversal**: entries with absolute paths, drive letters or `..`
  segments are rejected with an `unsafe_path` warning. Nothing is ever extracted
  to disk. Backslashes in names are treated as folder separators.
- **Filename encoding**: names are decoded as UTF-8 when the zip's UTF-8 flag
  is set, otherwise as CP437, unless the name is valid UTF-8 written without
  the flag (common). Names are NFC-normalised.
- **Duplicate entries**: the last one wins, with a `duplicate_entry` warning.
- **Ignored entries**: `__MACOSX/`, `._*`, `.DS_Store`, `Thumbs.db` and
  `desktop.ini` are OS artefacts from the user's machine, not platform content,
  and would only add noise to diffs. They are dropped, with one
  `ignored_entries` warning counting them. With `options.keep_ignored` they are
  listed as `unmatched` with `reason: ignored` instead.
- **Folders** are created for every path, whether or not the zip has an
  explicit entry for them; `modified` is only known when it has one.
- **Wrapper folder named like the zip**: unzipping an export and zipping it
  again puts everything below one folder named after the original zip
  (`instagram-johndoe-2026-09-29-AbCd1234/ads_information/…`). That name is
  personal and differs per export. If all entries (OS junk aside) lie below a
  single top-level folder whose name matches the zip's name without its
  extension (ignoring case and copy suffixes such as ` (1)`, ` 2` or
  ` - Copy`), the folder is dropped and its contents start at the container's
  root, with a `wrapper_folder` warning. This applies to nested zips too.
  A top-level folder named differently (`Takeout/`) stays.

---

## 6. Supported file types

| Parser     | Files                                                   | Notes                                                             | Status    |
|------------|---------------------------------------------------------|-------------------------------------------------------------------|-----------|
| `zip`      | `.zip`                                                  | Becomes a `container`.                                            | supported |
| `json`     | `.json`                                                 | Falls back to `jsonl` if the file has one value per line.         | supported |
| `jsonl`    | `.jsonl`, `.ndjson`, or `.json` with one value per line | Content is an array of the line values.                           | supported |
| `js-json`  | `.js` with `name = <json>`                              | JSON assigned to a variable, as in some platform exports.         | supported |
| `csv`      | `.csv`, `.tsv`                                          | Delimiter and quote sniffed (`.tsv`: tab). See [§3.2](#32-types). | supported |
| `html`     | `.html`                                                 | Needs a projection spec per platform; otherwise `unmatched`.      | planned   |
| `txt`      | `.txt`                                                  | Needs a projection spec; otherwise `unmatched`.                   | planned   |
| (media)    | images, video, audio                                    | `media` nodes, metadata only, detected by MIME.                   | supported |

---

## 7. Relation to JSON Schema

`type` uses the same type names as JSON Schema, and `properties` / `items`
mean the same thing. The main differences:

| This spec                | JSON Schema                                               |
|--------------------------|-----------------------------------------------------------|
| `shape`                  | closest to `format` (`date-time`, `email`, `uri`, `uuid`) |
| `format` (strftime)      | no direct equivalent; closest is `pattern`                |
| `stats`, `shapes`        | none (descriptive, not a validation rule)                 |
| `kind` and file metadata | none                                                      |

An exporter from a `data` subtree to JSON Schema (draft 2020-12) is therefore
straightforward and gives access to standard validators.

## 8. Worked example

A zip `export.zip` with two files at its top level:

```
export.zip
├── logins.csv
└── profile.json
```

**`profile.json`**: two nested objects and an array of objects

```json
{
  "user": {
    "name": "Anna Muster",
    "email": "anna@example.com",
    "joined": "2021-03-14T09:26:53Z"
  },
  "settings": {
    "language": "de",
    "notifications": true
  },
  "posts": [
    {"id": 101, "text": "Hello world", "likes": 3},
    {"id": 102, "text": "Zurich in autumn", "likes": 12, "location": "Zurich"},
    {"id": 103, "text": null, "likes": 0}
  ]
}
```

**`logins.csv`**

```csv
timestamp,action,device
1767225600,login,iPhone
1767312000,logout,
1767398400,login,MacBook
```

**Resulting schema document** (default options, so no values are kept)

```json
{
  "spec_version": "1.0",
  "parser_version": "0.1.0",
  "created_at": "2026-09-24T10:00:00+02:00",
  "source": {
    "name": "export.zip",
    "size_bytes": 688,
    "sha256": "a5b8b88090b64465fa41d6a1f49226a89b1fccf1e905dda95a4a23d8209b47aa"
  },
  "options": {
    "samples": false,
    "max_samples": 3,
    "masked_shapes": [
      "email",
      "url",
      "text",
      "alphanumeric",
      "uuid"
    ],
    "shape_threshold": 0.95,
    "max_depth": 3,
    "max_entries": 200000,
    "max_entry_size": 268435456,
    "max_total_size": 4294967296,
    "keep_ignored": false,
    "collapse_folders": [],
    "keep_folders": []
  },
  "warnings": [],
  "root": {
    "kind": "container",
    "name": "export.zip",
    "path": "",
    "size_bytes": 688,
    "ext": ".zip",
    "mime": "application/zip",
    "mime_source": "magic",
    "children": [
      {
        "kind": "file",
        "name": "logins.csv",
        "path": "/logins.csv",
        "size_bytes": 92,
        "modified": "2026-09-20T14:02:10",
        "ext": ".csv",
        "mime": "text/csv",
        "mime_source": "extension",
        "encoding": "utf-8",
        "parser": "csv",
        "csv": {
          "delimiter": ",",
          "quotechar": "\""
        },
        "type": "array",
        "length": {"min": 3, "max": 3},
        "stats": {"count": 1, "present": 1, "null": 0},
        "items": {
          "kind": "data",
          "name": null,
          "path": "/logins.csv/[]",
          "type": "object",
          "stats": {"count": 3, "present": 3, "null": 0},
          "properties": {
            "timestamp": {
              "kind": "data",
              "name": "timestamp",
              "path": "/logins.csv/[]/timestamp",
              "type": "integer",
              "shape": "unix_timestamp",
              "format": "s",
              "stats": {"count": 3, "present": 3, "null": 0},
              "shapes": {"unix_timestamp": 3}
            },
            "action": {
              "kind": "data",
              "name": "action",
              "path": "/logins.csv/[]/action",
              "type": "string",
              "shape": "alpha",
              "length": {"min": 5, "max": 6},
              "stats": {"count": 3, "present": 3, "null": 0},
              "shapes": {"alpha": 3}
            },
            "device": {
              "kind": "data",
              "name": "device",
              "path": "/logins.csv/[]/device",
              "type": "string",
              "shape": "alpha",
              "length": {"min": 0, "max": 7},
              "stats": {"count": 3, "present": 3, "null": 0},
              "shapes": {"alpha": 2, "empty": 1}
            }
          }
        }
      },
      {
        "kind": "file",
        "name": "profile.json",
        "path": "/profile.json",
        "size_bytes": 378,
        "modified": "2026-09-20T14:02:10",
        "ext": ".json",
        "mime": "application/json",
        "mime_source": "extension",
        "encoding": "utf-8",
        "parser": "json",
        "type": "object",
        "stats": {"count": 1, "present": 1, "null": 0},
        "properties": {
          "user": {
            "kind": "data",
            "name": "user",
            "path": "/profile.json/user",
            "type": "object",
            "stats": {"count": 1, "present": 1, "null": 0},
            "properties": {
              "name": {
                "kind": "data",
                "name": "name",
                "path": "/profile.json/user/name",
                "type": "string",
                "shape": "text",
                "length": {"min": 11, "max": 11},
                "stats": {"count": 1, "present": 1, "null": 0},
                "shapes": {"text": 1}
              },
              "email": {
                "kind": "data",
                "name": "email",
                "path": "/profile.json/user/email",
                "type": "string",
                "shape": "email",
                "length": {"min": 16, "max": 16},
                "stats": {"count": 1, "present": 1, "null": 0},
                "shapes": {"email": 1}
              },
              "joined": {
                "kind": "data",
                "name": "joined",
                "path": "/profile.json/user/joined",
                "type": "string",
                "shape": "datetime",
                "format": "%Y-%m-%dT%H:%M:%SZ",
                "length": {"min": 20, "max": 20},
                "stats": {"count": 1, "present": 1, "null": 0},
                "shapes": {"datetime": 1}
              }
            }
          },
          "settings": {
            "kind": "data",
            "name": "settings",
            "path": "/profile.json/settings",
            "type": "object",
            "stats": {"count": 1, "present": 1, "null": 0},
            "properties": {
              "language": {
                "kind": "data",
                "name": "language",
                "path": "/profile.json/settings/language",
                "type": "string",
                "shape": "alpha",
                "length": {"min": 2, "max": 2},
                "stats": {"count": 1, "present": 1, "null": 0},
                "shapes": {"alpha": 1}
              },
              "notifications": {
                "kind": "data",
                "name": "notifications",
                "path": "/profile.json/settings/notifications",
                "type": "boolean",
                "stats": {"count": 1, "present": 1, "null": 0}
              }
            }
          },
          "posts": {
            "kind": "data",
            "name": "posts",
            "path": "/profile.json/posts",
            "type": "array",
            "length": {"min": 3, "max": 3},
            "stats": {"count": 1, "present": 1, "null": 0},
            "items": {
              "kind": "data",
              "name": null,
              "path": "/profile.json/posts/[]",
              "type": "object",
              "stats": {"count": 3, "present": 3, "null": 0},
              "properties": {
                "id": {
                  "kind": "data",
                  "name": "id",
                  "path": "/profile.json/posts/[]/id",
                  "type": "integer",
                  "shape": "plain",
                  "stats": {"count": 3, "present": 3, "null": 0},
                  "shapes": {"plain": 3}
                },
                "text": {
                  "kind": "data",
                  "name": "text",
                  "path": "/profile.json/posts/[]/text",
                  "type": ["null", "string"],
                  "shape": "text",
                  "length": {"min": 11, "max": 16},
                  "stats": {"count": 3, "present": 3, "null": 1},
                  "shapes": {"text": 2}
                },
                "likes": {
                  "kind": "data",
                  "name": "likes",
                  "path": "/profile.json/posts/[]/likes",
                  "type": "integer",
                  "shape": "plain",
                  "stats": {"count": 3, "present": 3, "null": 0},
                  "shapes": {"plain": 3}
                },
                "location": {
                  "kind": "data",
                  "name": "location",
                  "path": "/profile.json/posts/[]/location",
                  "type": "string",
                  "shape": "alpha",
                  "length": {"min": 6, "max": 6},
                  "stats": {"count": 3, "present": 1, "null": 0},
                  "shapes": {"alpha": 1}
                }
              }
            }
          }
        }
      }
    ]
  }
}
```

**What to notice**

- **No personal data.** `Anna Muster`, the email address, the post texts and
  the timestamps appear nowhere in the schema, only their type, shape, length
  and counts.
- **Paths.** The root container has the empty path `""`. Every other path
  starts from inside the zip, and a file's keys continue its path directly
  (`/profile.json/user/email`); `/[]` steps into an array's items.
- **Files carry their content inline.** `profile.json` is itself the
  `object` node with `properties`; `logins.csv` is itself the `array` node.
- **CSV becomes an array of row objects.** The file node has `length` 3
  (rows), and its single `items` node describes all rows at once, with one
  property per column.
- **Type inference on CSV.** `timestamp` is `integer` although it is text in
  the file. It gets `unix_timestamp` / `s` because all values fall in the
  plausible range and the column is not an `id` column.
- **Empty vs. null.** The empty `device` cell counts as `shapes.empty`, not as
  `null`. `length.min` is therefore 0. The dominant shape
  is still `alpha`, because the threshold is measured over non-empty values
  (2 of 2).
- **Shape precedence.** `name` is `text`, not `alpha`, because of the space.
  `joined` is `datetime` with the trailing `Z` kept as a literal in `format`.
- **Arrays of objects are unified.** `posts` has one `items` node that
  describes all three posts together, just like the CSV rows.
- **Optional key.** `location` exists in only one of three posts:
  `stats.present` 1 of `count` 3.
- **Nullable value.** One `text` is `null`, so the type becomes the union
  `["null", "string"]` with `stats.null` 1. Nulls count in neither `shapes`
  nor `length`, so `shape` is still `text`.
- **Booleans** carry no `shape`.
- **Children are sorted by name**, so the same input always gives the same
  document.

## 9. Merging and comparing schemas

Two operations on schema trees support tracking a platform's format over time. Both work on
nodes and paths only; they never need the original exports.

### 9.1 Merging

`merge(documents)` combines the trees of several documents, e.g. several users' exports of the
same platform, into one tree: the basis of an *accepted* schema version. Nodes at the same path
are unified with the rules of [§3.4](#34-unification): `stats` and `shapes` are summed, types
form a union, the dominant `shape` and `format` are recomputed, `length` and `range` widen,
and a key missing from one document still counts that document's objects, so it shows as
optional. `files` and `folders` add up; `size_bytes` is summed and `modified` is the newest.

When the same path has different kinds in different documents, the more informative one is
kept, in this order: `file`, `container`, `folder`, `media`, `unmatched` (a file one export
could parse beats the same file another export failed on).

Alongside the tree, merging reports each path's **presence**: in how many of the documents it
occurs. A path present in every export is part of what the platform always delivers; one
present in few depends on how the account was used.

### 9.2 Comparing

`compare(base, new)` reports how `new` (e.g. a fresh upload) differs from `base` (e.g. the
accepted version):

| Category  | Meaning                                                                                                                                                                                                   |
|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `added`   | Paths only in `new`. Only the top of each added subtree is listed.                                                                                                                                        |
| `removed` | Paths only in `base`, listed the same way.                                                                                                                                                                |
| `moved`   | A removed and an added node with the same name and kind whose subtrees mostly match (at least half of their relative paths). Only unambiguous pairs count; a folder moved into a new folder is found too. |
| `changed` | Same path, different `kind`, type, `shape` or `format`.                                                                                                                                                   |

Only structure is compared, never counts, sizes or timestamps. Differences that depend on the
account's data rather than on the platform are ignored: whether a value was ever `null`, and the
shapes `mixed` and `empty`. Every path of either tree has a status (`added`, `removed`,
`moved_from`, `moved_to`, `changed` or `unchanged`); descendants share their subtree's.

A path missing from one upload is not necessarily gone from the platform: that user may just
never have used the feature. Comparing against a merged version with presence counts helps to
tell the two apart.


### 9.3 Suggesting correspondences

A data point keeps its meaning when its location changes: a file or key moves, is renamed, or is
named differently because the export was requested in another language (`Date` in English,
`Datum` in German). `suggest(known, new)` proposes, for every **data point** of `new` whose path
is not in `known`, which known paths it may correspond to. A **data point** (`is_data_point`) is
a value or a **list** in parsed content, a list's **item** (`…/[]`: the value or entity it
holds), a parsed file whose content is a list (a JSON array, a CSV's rows), or a **media** file.
Objects only group keys unless they are a list's item, and other parsed and unmatched files,
folders and containers only describe where data lies: they get no suggestions,
though renamed objects and files are still followed so that their content can be matched. Lists and
objects, even empty ones, are **structures** (`is_structure`).

| Reason    | When                                                                                                                                                                                                                                | Score                                                                                                                                                                                                                                                  |
|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `moved`   | The node lies in a subtree that `compare` found moved, or below a list/object with one clear `renamed` candidate, and its relative path exists there.                                                                               | 1.0 for moves; below a rename, the rename's score                                                                                                                                                                                                      |
| `renamed` | Its parent is known (directly, through a move or through a rename), and a known sibling of the same kind, type, shape and format is absent from `new`. Lists and objects must also share at least half of their relative sub-paths. | 0.5, +0.3 at the same position among its siblings; values: +0.2 with the same `format` (else +0.1 with the same `shape`); lists/objects: +0.2 × the share of sub-paths in common. Multiplied by the parent's score when the parent was itself renamed. |

Nodes are handled parents first. When a list or object gets exactly one best `renamed`
candidate, its children are matched through it, so a translated object carries its translated
keys along (`Kommentare/Datum` → `Comments/Date`). Candidates are sorted by score. They are
suggestions only: deciding that two paths hold the same information is a curator's call.
