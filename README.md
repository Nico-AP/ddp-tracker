# ddp2json

Convert platform **Data Download Package** (DDP) ZIP archives into nested JSON
reports. By default each report is a **fully redacted schema** (types and shapes
only).

**Version:** 0.1.0

## Install

Requires Python 3.10+.

```bash
# From the repo (editable)
pip install -e ".[dev]"

# Or runtime deps only
pip install -e .
```

## Usage

On a TTY you may omit `--platform` and pick once per ZIP. Non-interactive runs
(CI, scripts) **require** `--platform`.

### 1. fully redacted schema (default)

```bash
ddp2json data/input data/output --platform facebook
# → <stem>.schema.json
```

### 2. schema with enums (debugging)

```bash
# safe enums (short non-PII values; paths scrubbed)
ddp2json data/input data/output --platform tiktok --enums
# → <stem>.schema-enums.json

# schema with full enums (all enum values; original paths)
ddp2json data/input data/output --platform instagram --schema-full
# → <stem>.schema-full.json

# HTML specs directory can be manually overwritten for these modes
ddp2json data/input data/output --platform facebook --enums --html-specs path/to/specs
```

### 3. full, unredacted content tree

```bash
# Unredacted content tree (full HTML DOM and raw field values)
ddp2json data/input data/output --platform google --full
# → <stem>.json
```

### Summary

| CLI | scrubs path | Enum `values` | Data | HTML |
|-----|------------|---------------|------|------|
| *(default)* | yes | none | descriptors | specs → fields, else **unmatched** |
| `--enums` | yes | safe non-PII | descriptors | specs → fields, else **unmatched** |
| `--schema-full` | no | all scalars | descriptors | specs → fields, else **unmatched** |
| `--full` | no | n/a | raw leaves | full DOM |

Known `--platform` values: `facebook`, `instagram`, `tiktok`, `unknown`. Any 
other non-empty string is accepted as a custom label (used for HTML spec 
matching and report meta). Use `google` for Google/YouTube Takeout exports 
(`youtube` is a registry alias, not a built-in conversion label). Pass 
`--platform` to apply one label to every ZIP; omit it on a TTY to be prompted 
**per archive**.

Exit status is **non-zero** if any archive fails.

## Output

The report’s ``tree`` is a nested dict mirroring the archive. Nodes are either
plain objects (directories / JSON objects) or tagged with a ``kind``. Canonical
constructors live in [`ddp2json/engine/tree/nodes.py`](ddp2json/engine/tree/nodes.py).

| `kind` | Role | Typical fields |
|--------|------|----------------|
| `data` | Scalar value (JSON/CSV cell, projected HTML text, TXT field, …) | Full: `value`. Schema: `type`, `shape`, optional `length` / `format` / `values` |
| `media` | Image / video / audio file | `path`, `size`, `modified`, `ext`, `mime` |
| `unmatched` | Not parsed / not projected (failed parse, HTML without a spec, other non-media files) | same meta as media |

### Data

**Full mode**

```json
{"kind": "data", "value": "hello"}
```

**Schema modes** (`value` is replaced by descriptors)

```json
{
  "kind": "data",
  "type": "string",
  "shape": "datetime",
  "length": 19,
  "format": "%Y-%m-%d %H:%M:%S"
}
```

- `type` — JSON-ish type: `string`, `integer`, `number`, `boolean`, `null`, …
- `shape` — structural label: `email`, `url`, `unix_timestamp`, `datetime`,
  `date`, `text`, `empty`, `alpha`, …
- `format` — optional; for `date` / `datetime` a strftime pattern; for
  `unix_timestamp` either `s` or `ms`
- `length` — string length (and ranges after list unify); empty stubs use `0`
- `values` — optional enum sample: omitted in default `schema`; safe non-PII in
  `--enums`; all scalars in `--schema-full`

### Media / unmatched

```json
{
  "kind": "media",
  "path": "photos/IMG_001.jpg",
  "size": 12345,
  "modified": "2024-01-10 12:00:00",
  "ext": ".jpg",
  "mime": "image/jpeg"
}
```

In schema modes with path scrubbing, identifying segments in `path` may be
replaced (e.g. `{email}`, hashed FB thread folders).

### Other node kinds

| `kind` | Role |
|--------|------|
| `list` | Ordered collection. Build: `items` map `"0"`, `"1"`, …. Schema unify: often `{length, item}` |
| `html` | HTML file before projection: same meta as media plus `dom` (element tree). Only in the content tree / `--full`; schema modes project or mark `unmatched` |
| `variants` | Schema only: incompatible shapes under one field — `{options: [...]}` |

Directories and JSON objects are **plain dicts** (no `kind`). Schema nodes may
also carry `optional: true` when a field is missing from some list items.

### HTML `dom` (inside `kind: html`)

Elements are plain objects with string `tag`, optional `attrs`, and
`children` as a `list` of elements or `data` text leaves. Empty `attrs` are
omitted; script/style/comments are skipped at parse time.

## Python API

```python
from pathlib import Path
from ddp2json import process_archive

report = process_archive(
    Path("export.zip"),
    Path("/tmp/ddp-extract"),
    mode="schema",
    platform="facebook",
)
```

| Symbol | Role |
|--------|------|
| `main(argv=None)` | CLI entry (`ddp2json` / `python -m ddp2json`); exits `1` on failure |
| `process_archive(zip_path, tmp_root, mode=..., platform=..., html_specs_dir=...)` | One archive → report `dict` (`generated_at`, `archive`, `platform`, `mode`, `summary`, `tree`); **`platform` required** |

`mode` is one of `schema` (default), `schema_enums`, `schema_full`, or `full` — same as the CLI flags above.

## Contributing

The package is split into two main folders:

| | Path | When to edit |
|---|------|----------------|
| **Policy** | [`ddp2json/policy/`](ddp2json/policy/) | Adding HTML projection specs or changing scrub / empty-section rules |
| **Engine** | [`ddp2json/engine/`](ddp2json/engine/) | Changing how conversion / redaction / projection *runs* |

### Policy

- Scrub lists / path patterns: [`ddp2json/policy/scrub/`](ddp2json/policy/scrub/).
- Empty-section phrases: [`ddp2json/policy/empty.py`](ddp2json/policy/empty.py).
- HTML specs: [`ddp2json/policy/html/`](ddp2json/policy/html/).

**HTML specs** (recursive `*.json`; skips `_`-prefixed paths). *No active specs
ship with the package*—only `policy/html/_examples/*.json.example`. Copy an
example to a real `*.json` (or pass `--html-specs`) before schema modes will
project HTML; otherwise HTML becomes `unmatched`.

```json
{
  "id": "example_title_and_links",
  "platforms": ["*"],
  "match": "**/*.html",
  "extract": {
    "title": {"select": "title", "take": "text"},
    "links": {
      "select": "a[href]",
      "take": "list",
      "fields": {
        "href": {"take": "attr", "name": "href"},
        "text": {"take": "text"}
      }
    }
  }
}
```

- `platforms`: `*` or any known/custom `--platform` label
- `match`: glob against the HTML node’s `path`
- `extract`: CSS `select` + `take` of `text`, `attr` (+ `name`), or `list` (+ `fields`)
- Nested `select` inside list `fields` scopes to each matched item

### Formatting & tests

[Black](https://black.readthedocs.io/) (line length 88; `pyproject.toml`):

```bash
pip install -e ".[dev]"
black .
black --check .
pytest
```
