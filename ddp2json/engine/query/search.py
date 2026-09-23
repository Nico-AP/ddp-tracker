"""Walk / search helpers for archive content trees."""

from __future__ import annotations

from collections.abc import Iterator

from ..tree.nodes import is_leaf, is_list


def _children(node: dict) -> dict:
    """Return the child map for a directory, object, list, or variants node."""
    if is_list(node):
        # Summarized uniform list: one representative under {n}.
        if "item" in node and "items" not in node:
            return {"{n}": node["item"]}
        items = node.get("items")
        return items if isinstance(items, dict) else {}
    if node.get("kind") == "variants":
        options = node.get("options") or []
        return {str(i): opt for i, opt in enumerate(options)}
    return {k: v for k, v in node.items() if k not in ("optional", "taxonomy")}


def walk_leaves(tree: dict, prefix: str = "") -> Iterator[tuple[str, dict]]:
    """Yield (slash-path, leaf) for every data/media/unmatched leaf under tree.

    List nodes contribute their item indices to the path (not the literal
    key "items"), e.g. messages/0/content.
    """
    if is_leaf(tree):
        yield prefix, tree
        return

    for key, child in _children(tree).items():
        path = f"{prefix}/{key}" if prefix else str(key)
        if is_leaf(child):
            yield path, child
        elif isinstance(child, dict):
            yield from walk_leaves(child, path)
