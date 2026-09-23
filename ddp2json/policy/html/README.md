# HTML projection specs (prescriptions only)

Add or edit ``*.json`` files in this directory (and subfolders) to teach
schema modes how to project HTML DOMs into semantic fields.

**Do not** change Python under ``ddp2json/engine/`` when adding a platform
page — that is the projector/runtime. Only extend the engine if a spec cannot
express what you need with ``select`` / ``take`` / ``fields``.

## Quick start

```bash
cp _examples/example_title_and_links.json.example ./my_page.json
# edit id, platforms, match, extract
python -m ddp2json data/input data/output
```

Only ``*.json`` files are loaded (recursive). Files under ``_examples/`` and
``*.json.example`` are ignored.

## Spec shape

```json
{
  "id": "unique_stable_id",
  "platforms": ["facebook"],
  "match": "**/*.html",
  "extract": {
    "title": {"select": "title", "take": "text"}
  }
}
```

- ``platforms``: ``*`` or ``facebook`` / ``instagram`` / ``tiktok`` / ``google`` / ``unknown``
- ``match``: path glob against the HTML node's ``path``
- ``extract``: CSS ``select`` + ``take`` of ``text``, ``attr`` (+ ``name``), or ``list`` (+ ``fields``)

Override the specs directory at runtime with ``--html-specs DIR``.

**Note:** This package ships **no active ``*.json`` specs** by default—only
``_examples/*.json.example``. Until you add specs (or pass ``--html-specs``),
schema modes mark every HTML file as ``kind: "unmatched"`` (DOM dropped).
