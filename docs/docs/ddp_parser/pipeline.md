# Parser: pipeline and package structure (technical reference)

!!! note "For developers"
    How the `ddp_parser` package (`packages/ddp-parser/`) turns a DDP into the schema document
    described in [Parser: schema format](index.md), and how the package is organised. To use the
    DDP Tracker, see the [user guide](../index.md).

**Scope of the current implementation:** zip, JSON (incl. JSON Lines and `js-json`), CSV and media
detection. HTML and TXT will follow in a future release.

**Out of scope for the package:** platforms, storage, annotations and ontologies.
These are part of the platform package in the Django app.
The parser knows nothing about them; its
only job is to produce a stable, serialisable `Document`.

## Pipeline

```
input (path | bytes | IO)
  │
  ▼ 1. SOURCE     open_input(): name, size, sha256; zip? → read_zip() : one Entry
  │               yields Entry(parts, size, modified, open())
  │               · name decoding (UTF-8 flag / CP437 / heuristic), NFC
  │               · unsafe paths, duplicates, entry limit → warnings; OS junk dropped
  │               · ReadBudget: per-entry / total size → unmatched(too_large)
  │               · nested *.zip → read_zip() again (depth ≤ max_depth)
  │               · a single top-level folder named like the zip → dropped (unwrap)
  ▼ 2. PLAN       central directory is known up front, so:
  │               · build folder skeleton (implicit dirs included)
  │               · collapse look-alike folders  johndoe_1234/ … → {*}/  (rules, heuristic)
  │               · group numbered siblings  message_1.json … → message_{n}.json
  ▼ 3. CLASSIFY   ext + magic bytes → mime, mime_source; pick Parser or media/unmatched
  ▼ 4. PARSE      parser_for(name)(bytes) → Parsed(parser, encoding, csv/wrapper…)
  │                                   + iterator of values (one per file; rows for csv; lines for jsonl)
  │               failure → unmatched(parse_error, error)
  ▼ 5. OBSERVE    every value is fed to ONE NodeBuilder per parsed file
  │               (a group shares one builder → merging files = observing them all)
  │               observe(value): types, null/present counts, shape counts,
  │               length min/max, date-format candidates, object keys → child builders,
  │               array items → single items builder
  ▼ 6. BUILD      builder.build() → frozen DataNode (a file's inline fields): count derived
  │               from parent, dominant shape vs threshold / mixed, format / formats /
  │               ambiguity warning, type unions, samples
  ▼ 7. NORMALIZE  normalize(root): variable object keys → {*}, their nodes merged
  │               (rules, key shape, shared words, look-alike values); warning paths renamed
  ▼ 8. ASSEMBLE   Document(spec_version, parser_version, created_at, source, options,
                  warnings, root)  →  to_dict / to_json / from_dict
```

### Design choices

- **Stream and aggregate; never hold all the values.** A raw value exists only while it is
  being observed, so memory grows with the size of the schema, not the export. Zip members are
  read with `zf.open()` and never extracted to disk. JSON files are loaded with `json.load` for
  now. The parser interface allows swapping in a streaming parser (e.g. `ijson`) for large files
  without touching schematization.
- **One builder, one `observe()`.** Unifying array items, merging grouped files and
  aggregating CSV rows are all the same operation: observing more values into the same
  `NodeBuilder`. There is no separate merge/unify pass and no "variants" node.
- **`count` is derived, not tracked.** A builder counts how many objects it has seen,
  and every property's `count` is that number. A key first seen late therefore comes out right
  automatically (optional ⇔ `present < count`).
- **Grouping happens before parsing,** based on the entry list, so grouped files stream straight
  into one shared builder.
- **Immutable output model.** Frozen [msgspec](https://jcristharris.com/msgspec/) Structs: the
  class definitions *are* the JSON format (a union tagged by `kind`, field order = key order,
  unset optional fields omitted), and decoding validates. The JSON / dict round-trip is the
  contract downstream consumers rely on.

## Package structure

```
packages/ddp-parser/
  pyproject.toml
  README.md
  tests/
  src/ddp_parser/
    __init__.py        # public API: parse(source, options=None) -> Document; Options; Document
    py.typed
    options.py         # Options: samples, max_samples, masked_shapes, shape_threshold, max_depth, limits, …
    pipeline.py        # orchestrates steps 1–8; the only module that knows the whole flow
    errors.py          # LimitExceeded, ParseError, UnsafePath, …
    merge.py           # merge(documents): one tree + presence per path (spec 9.1)
    compare.py         # compare(base, new): added / removed / moved / changed (spec 9.2)
    normalize.py       # normalize(root, options): variable object keys → {*} (spec 3.6)
    similarity.py      # look_alike(): shared by folder collapsing and variable keys
    __main__.py        # dev CLI: python -m ddp_parser export.zip > schema.json

    model/             # output contract (pure data, no I/O)
      paths.py         #   JSON Pointer paths: escape / join / split; matches() for rules
      nodes.py         #   Kind, Shape, …; Container/Folder/File/Media/Unmatched/DataNode
      document.py      #   Document, Source, ParseWarning
      walk.py          #   walk(node): a node and all its descendants
      serialize.py     #   to_json / from_json / to_dict / from_dict (msgspec)

    source/            # steps 1–3
      __init__.py      #   open_input(): path / bytes / stream → name, size, sha256
      entry.py         #   Entry; ReadBudget (size limits on what is read)
      zip.py           #   read_zip(): names, unsafe paths, OS junk, duplicates, entry limit
      unwrap.py        #   drop a top-level folder named like its zip (re-zipped exports)
      plan.py          #   folder tree of a container's entries; folders collapsed, files grouped
      grouping.py      #   numbered-sibling detection → group pattern; folder-name masks
      mime.py          #   MIME (magic → extension), media check, nested-zip check

    parsers/           # step 4
      __init__.py      #   parser_for(name): extension → parser
      base.py          #   Parsed: parser details + one value or lazily produced array items
      encoding.py      #   BOM → UTF-8 → cp1252
      json.py          #   json (with jsonl fallback), jsonl, js-json
      csv.py           #   dialect sniffing, header cleanup, cell type inference, row dicts

    schematize/        # steps 5–6
      builder.py       #   NodeBuilder: observe() values, build() the frozen DataNode
      shapes.py        #   scalar shape classifiers (ordered, first match wins)
      date_formats.py  #   strftime candidates, all-values intersection, tz / fractions
      samples.py       #   opt-in sample collection + masking
```

### Rationale

Each subpackage owns one or more steps of the pipeline and depends only on the layers below it:
`model` ← `schematize` ← `parsers` ← `source` ← `pipeline`. `model` depends on nothing.

- **`src/` layout, separate workspace member.** Tests run against the installed package, so an
  accidental Django import or missing file shows up immediately. The distribution is
  `ddp-parser` (hyphen) and the import name is `ddp_parser` (underscore).
- **`__init__.py` is the only public API.** The Django app imports from here only, so everything
  else can be reorganised freely.
- **`options.py`** holds every tunable from the spec in one frozen object. It is copied into
  `Document.options`, so a stored schema records how it was produced.
- **`errors.py`**: specific exceptions that `pipeline` turns into `unmatched` nodes or
  `warnings`. This avoids broad `except Exception`.
- **`model/`** is the output contract: pure data, no I/O. It is not called "schema" because that
  word already means the whole document, and not "models" because that means database tables in
  Django. `paths.py` holds the JSON Pointer helpers that every layer uses to build paths, the
  basis for diffing. `serialize.py` is a thin msgspec wrapper that also turns decoding errors
  into `InvalidDocumentError`.
- **`source/`** is named after where files come from, not "zip": a single file is also a source
  (one `Entry`), and so is a nested zip. Everything zip-specific stays in `zip.py`. Parsers only
  ever see an entry's bytes. Grouping lives here because it runs on the entry list before any
  parsing. `mime.py` is not called `filetype.py` to avoid clashing with the `filetype`
  package it uses for magic-byte detection.
- **`parsers/`** turn a file's bytes into plain Python values (dict, list, scalars) in a
  `Parsed` record. They know nothing about schematization, so HTML/TXT, or a streaming JSON
  parser, can be added without touching anything else. The pipeline asks `parser_for()` and
  never imports a concrete parser. Encoding detection lives here because parsers are what need
  it. It is deterministic (BOM → UTF-8 → cp1252) rather than statistical: charset-normalizer
  misread Western legacy files as cp1250/cp1257, and a guess that varies with a file's contents
  would make schemas drift between exports.
- **`schematize/`**: `NodeBuilder` follows the builder pattern: `observe()` only counts, and
  `build()` makes every decision that needs all values seen (dominant shape, format,
  ambiguity) and returns the frozen node. Single-value classification (`shapes.py`,
  `date_formats.py`) is made of pure functions that are easy to check against the spec tables.
  Module names are short nouns read in the package's context ("schematize: shapes"). `samples.py` is opt-in and privacy-sensitive, so it is kept separate and easy to
  audit.

## Build order (round 1)

1. `model/`, including the `paths.py` helpers and the serialize round-trip. *(done)*
2. `schematize/`: shapes, date formats, builder, samples, tested directly on Python values. *(done)*
3. `parsers/`: json, jsonl, js-json, csv. *(done)*
4. `source/`: single file, then zip (limits, traversal, ignored, nesting), then grouping. *(done)*
5. `pipeline.py`, `parse()` and the CLI. Golden test: the [worked example](index.md#8-worked-example). *(done)*

## Usage

```python
from ddp_parser import Options, parse, to_json

document = parse("export.zip")  # path, bytes (pass name=) or binary stream
document = parse(data, Options(samples=True), name="posts.json")
print(to_json(document))
```

```bash
uv run python -m ddp_parser export.zip --collapse /messages/inbox > schema.json
```

`parse()` only raises for an input that looks like a zip but cannot be opened (`ParseError`)
or cannot be read at all (`OSError`); every problem inside the input becomes an `unmatched`
node or a document warning.

## Notes

- **Partly read group members.** A file of a group that fails halfway (a bad line in JSON Lines,
  a broken CSV row) has its earlier rows counted already; the file itself is reported in the
  `group_member_failed` warning.
