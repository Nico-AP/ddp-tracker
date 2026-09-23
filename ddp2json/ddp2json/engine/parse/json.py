"""Parse JSON files into a nested tree of data leaves and list nodes.

Objects become plain nested dicts; arrays become
{"kind": "list", "items": {"0": ..., "1": ..., ...}}; scalars become
{"kind": "data", "value": ...}. Meta latin-1/UTF-8 mojibake is repaired on
string scalars.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..tree.nodes import data_leaf, list_node


def fix_mojibake(text: str) -> str:
    """Repair Meta's latin-1/UTF-8 double-encoding (e.g. "ð\x9f\x98©" -> "😩").

    Meta (Facebook/Instagram) exports write UTF-8 bytes but escape them as
    latin-1 code points. Re-encoding as latin-1 and decoding as UTF-8 reverses
    it. The repair is only applied when that round-trip succeeds, so clean
    ASCII and already-correct text (e.g. YouTube/TikTok) are left untouched.
    """
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired


def _clean(value):
    """Repair Meta mojibake on string scalars; leave other types as-is."""
    return fix_mojibake(value) if isinstance(value, str) else value


def to_tree(value) -> dict:
    """Convert parsed JSON into a nested dict of data leaves / list nodes."""
    if isinstance(value, dict):
        return {str(k): to_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return list_node({str(i): to_tree(item) for i, item in enumerate(value)})
    return data_leaf(_clean(value))


def parse_json_tree(file_path: Path) -> dict:
    """Load one JSON file and return its nested data-leaf tree."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        content = json.load(f)
    tree = to_tree(content)
    # Top-level scalar → single-item list so the file node stays directory-like.
    if tree.get("kind") == "data":
        return list_node({"0": tree})
    return tree
