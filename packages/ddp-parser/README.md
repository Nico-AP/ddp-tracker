# ddp-parser

Turns a platform data download package (a zip or a single file) into a schema document
that describes its structure (files, keys, types, shapes, counts) without personal data.

The output format is specified in [`docs/docs/ddp_parser/index.md`](../../docs/docs/ddp_parser/index.md),
the pipeline and package layout in [`docs/docs/ddp_parser/pipeline.md`](../../docs/docs/ddp_parser/pipeline.md).

This package is framework-agnostic: it knows nothing about Django, platforms or storage.

## Usage

```python
from ddp_parser import parse, to_json

document = parse("export.zip")
print(to_json(document))
```

```bash
uv run python -m ddp_parser export.zip > schema.json
```
