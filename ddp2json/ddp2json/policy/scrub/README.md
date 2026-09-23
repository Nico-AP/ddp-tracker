# Scrub policy

Edit Python modules here to change privacy rules used by schema modes:

- [`fields.py`](fields.py) — blocked field names, sensitive shapes, enum size limits
- [`path_patterns.py`](path_patterns.py) — regexes for identifying path segments

The runners that *apply* these rules live under `ddp2json/engine/schema/`
(`describe.py`, `path_redact.py`). Do not put HTML projection specs here —
those belong in [`../html/`](../html/).
