"""Load HTML projection specs from ``policy/html`` (or an override directory)."""

from __future__ import annotations

import json
from pathlib import Path


def default_specs_dir() -> Path:
    """Bundled HTML specs under ``ddp2json/policy/html``."""
    # engine/schema/html/loader.py → package root ddp2json/
    return Path(__file__).resolve().parents[3] / "policy" / "html"


def load_specs(specs_dir: Path | None = None) -> list[dict]:
    """Load and validate ``*.json`` specs recursively, sorted by ``id``.

    Skips ``_examples/`` directories and non-``.json`` files.
    """
    directory = specs_dir if specs_dir is not None else default_specs_dir()
    if not directory.is_dir():
        return []

    specs: list[dict] = []
    for path in sorted(directory.rglob("*.json")):
        if any(part.startswith("_") for part in path.relative_to(directory).parts):
            continue
        with path.open("r", encoding="utf-8") as f:
            spec = json.load(f)
        if not isinstance(spec, dict):
            raise ValueError(f"HTML spec must be a JSON object: {path}")
        spec_id = spec.get("id")
        if not spec_id or not isinstance(spec_id, str):
            raise ValueError(f"HTML spec missing string 'id': {path}")
        if "extract" not in spec or not isinstance(spec["extract"], dict):
            raise ValueError(f"HTML spec missing object 'extract': {path}")
        if "match" not in spec:
            spec["match"] = "**/*.html"
        if "platforms" not in spec:
            spec["platforms"] = ["*"]
        specs.append(spec)

    specs.sort(key=lambda s: s["id"])
    return specs
