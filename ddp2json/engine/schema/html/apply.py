"""Walk a content tree and project or strip HTML nodes for schema modes."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from ...tree.nodes import is_html, is_list, unmatched_leaf
from .loader import load_specs
from .project import project_dom


def _platform_matches(spec: dict, platform: str) -> bool:
    """True if the spec’s ``platforms`` list includes ``platform`` or ``*``."""
    platforms = spec.get("platforms") or ["*"]
    return "*" in platforms or platform in platforms


def _path_matches(spec: dict, path: str) -> bool:
    """True if ``path`` matches the spec’s ``match`` glob (incl. ``**/`` forms)."""
    pattern = spec.get("match") or "**/*.html"
    # fnmatch does not treat ** specially; also try basename and full path.
    if fnmatch(path, pattern):
        return True
    # Common convenience: **/*.html style → match any path ending with suffix
    if pattern.startswith("**/"):
        suffix = pattern[3:]
        if fnmatch(path, suffix) or fnmatch(path.split("/")[-1], suffix):
            return True
        # any directory prefix
        parts = path.split("/")
        for i in range(len(parts)):
            candidate = "/".join(parts[i:])
            if fnmatch(candidate, suffix):
                return True
    return False


def find_matching_spec(specs: list[dict], *, platform: str, path: str) -> dict | None:
    """Return the first matching spec (specs must already be sorted by id)."""
    for spec in specs:
        if _platform_matches(spec, platform) and _path_matches(spec, path):
            return spec
    return None


def _html_to_unmatched(node: dict) -> dict:
    """Strip an HTML wrapper to an unmatched leaf (drop DOM)."""
    return unmatched_leaf(
        node.get("path") or "",
        int(node.get("size") or 0),
        node.get("modified"),
    )


def apply_html_specs(
    tree: dict,
    *,
    platform: str,
    specs_dir: Path | None = None,
    specs: list[dict] | None = None,
) -> dict:
    """Replace HTML nodes: project via matching spec, else unmatched leaf.

    Leaves non-HTML structure intact. Intended for schema modes only; ``--full``
    keeps the DOM as built.
    """
    loaded = specs if specs is not None else load_specs(specs_dir)

    def walk(node):
        if not isinstance(node, dict):
            return node

        if is_html(node):
            path = node.get("path") or ""
            spec = find_matching_spec(loaded, platform=platform, path=path)
            if spec is None:
                return _html_to_unmatched(node)
            dom = node.get("dom") or {}
            return project_dom(dom, spec.get("extract") or {})

        if is_list(node):
            items = node.get("items") or {}
            return {
                "kind": "list",
                "items": {str(k): walk(v) for k, v in items.items()},
            }

        # Plain object / directory: recurse values; leave kind wrappers alone
        if "kind" in node:
            return node

        return {str(k): walk(v) for k, v in node.items()}

    return walk(tree)
