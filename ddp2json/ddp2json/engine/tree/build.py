"""Build a nested content tree from an extracted DDP archive.

This stage is structure-only: fix encodings, expand JSON/CSV/HTML/TXT, attach
media or unmatched leaves. Privacy redaction (paths, values) happens later in
``ddp2json.engine.schema``; HTML projection via specs happens in the pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipInfo

from ..parse.csv import parse_csv_tree
from ..parse.html import parse_html_tree
from ..parse.json import parse_json_tree
from ..parse.txt import parse_txt_tree
from .nodes import file_leaf, unmatched_leaf
from .paths import (
    fix_zip_name,
    is_appledouble,
    is_real_csv,
    is_real_html,
    is_real_json,
    is_real_txt,
)


def format_modified(date_time: tuple[int, ...]) -> str | None:
    """Format a ZIP date_time; return None for the 1980-00-00 sentinel."""
    text = "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*date_time)
    if text == "1980-00-00 00:00:00":
        return None
    return text


def _set_path(root: dict, parts: tuple[str, ...], value) -> None:
    """Set root[parts[0]]...[parts[-1]] = value, creating dicts along the way."""
    if not parts:
        return
    node = root
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _ensure_dir(root: dict, parts: tuple[str, ...]) -> None:
    """Ensure a directory path exists as nested empty/partial dicts."""
    node = root
    for part in parts:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child


def build_tree(extracted_dir: Path, info_list: list[ZipInfo]) -> dict:
    """Build the content tree for one archive from its zip member list."""
    root: dict = {}

    for info in info_list:
        raw_path = info.filename
        if is_appledouble(raw_path):
            continue

        path = fix_zip_name(raw_path)
        is_dir = raw_path.endswith("/")
        parts = Path(path.rstrip("/")).parts
        if not parts:
            continue

        tree_path = "/".join(parts)

        if is_dir:
            _ensure_dir(root, parts)
            continue

        disk_path = extracted_dir / raw_path
        modified = format_modified(info.date_time)

        if is_real_csv(path):
            try:
                subtree = parse_csv_tree(disk_path)
                _set_path(root, parts, subtree)
                print(f"    + csv {tree_path}")
            except Exception as exc:
                print(f"    x failed {tree_path}: {exc}", file=sys.stderr)
                _set_path(
                    root,
                    parts,
                    unmatched_leaf(tree_path, info.file_size, modified),
                )
            continue

        if is_real_json(path):
            try:
                subtree = parse_json_tree(disk_path)
                _set_path(root, parts, subtree)
                print(f"    + json {tree_path}")
            except Exception as exc:
                print(f"    x failed {tree_path}: {exc}", file=sys.stderr)
                _set_path(
                    root,
                    parts,
                    unmatched_leaf(tree_path, info.file_size, modified),
                )
            continue

        if is_real_html(path):
            try:
                subtree = parse_html_tree(
                    disk_path,
                    tree_path=tree_path,
                    size=info.file_size,
                    modified=modified,
                )
                _set_path(root, parts, subtree)
                print(f"    + html {tree_path}")
            except Exception as exc:
                print(f"    x failed {tree_path}: {exc}", file=sys.stderr)
                _set_path(
                    root,
                    parts,
                    unmatched_leaf(tree_path, info.file_size, modified),
                )
            continue

        if is_real_txt(path):
            try:
                subtree = parse_txt_tree(disk_path)
                _set_path(root, parts, subtree)
                print(f"    + txt {tree_path}")
            except Exception as exc:
                print(f"    x failed {tree_path}: {exc}", file=sys.stderr)
                _set_path(
                    root,
                    parts,
                    unmatched_leaf(tree_path, info.file_size, modified),
                )
            continue

        _set_path(root, parts, file_leaf(tree_path, info.file_size, modified))

    return root
