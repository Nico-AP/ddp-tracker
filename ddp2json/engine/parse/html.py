"""Parse HTML files into an html wrapper node with a DOM subtree.

Each element is a plain object; text content is a data leaf; children are a
list node. ``tag`` and attribute values are plain strings (structural, not
content). Empty ``attrs`` are omitted::

    {
      "kind": "html",
      "path": "...",
      "size": ...,
      "modified": "...",
      "ext": ".html",
      "mime": "text/html",
      "dom": {
        "tag": "html",
        "children": {"kind": "list", "items": {...}}
      }
    }

Comment, script, and style nodes are skipped. Empty elements (no attrs, no
children) are dropped. A wrapper with no attrs and a single text child is
collapsed to that data leaf.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from ..tree.nodes import data_leaf, html_node, list_node

_SKIP_TAGS = frozenset({"script", "style"})
# Keep even when they have no children / no attrs (void or meaningful alone).
_KEEP_EMPTY_TAGS = frozenset(
    {
        "img",
        "br",
        "hr",
        "input",
        "meta",
        "link",
        "source",
        "wbr",
        "area",
        "col",
        "embed",
        "param",
        "track",
    }
)


def _attr_value(value) -> str:
    """Normalize a BeautifulSoup attribute value to a string."""
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def _element_node(tag_name: str, attrs: dict, children: dict) -> dict:
    """Build an element object; omit ``attrs`` when empty."""
    node: dict = {
        "tag": tag_name,
        "children": list_node(children),
    }
    if attrs:
        node["attrs"] = attrs
    return node


def _element_to_dom(tag: Tag) -> dict | None:
    """Convert one BeautifulSoup Tag into a DOM node, or None if empty."""
    attrs = {str(name): _attr_value(val) for name, val in tag.attrs.items()}
    children: dict = {}
    idx = 0
    for child in tag.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            text = str(child)
            if not text.strip():
                continue
            children[str(idx)] = data_leaf(text)
            idx += 1
            continue
        if isinstance(child, Tag):
            if child.name and child.name.lower() in _SKIP_TAGS:
                continue
            node = _element_to_dom(child)
            if node is None:
                continue
            children[str(idx)] = node
            idx += 1

    # Collapse attr-less single-text wrappers to the data leaf.
    if not attrs and len(children) == 1:
        only = next(iter(children.values()))
        if isinstance(only, dict) and only.get("kind") == "data":
            return only

    # Drop empty elements (no attrs, no remaining children), except void tags.
    tag_name = (tag.name or "").lower()
    if not attrs and not children and tag_name not in _KEEP_EMPTY_TAGS:
        return None

    return _element_node(tag.name, attrs, children)


def _root_dom(soup: BeautifulSoup) -> dict:
    """Pick the document root element (prefer <html>, else first Tag)."""
    if soup.html is not None:
        node = _element_to_dom(soup.html)
        if node is not None and node.get("kind") != "data":
            return node
        # Collapsed or empty html — wrap text if needed.
        if node is not None and node.get("kind") == "data":
            return _element_node("html", {}, {"0": node})
    for child in soup.children:
        if isinstance(child, Tag) and child.name:
            if child.name.lower() in _SKIP_TAGS:
                continue
            node = _element_to_dom(child)
            if node is None:
                continue
            if node.get("kind") == "data":
                return _element_node(child.name, {}, {"0": node})
            return node
    return _element_node("html", {}, {})


def parse_html_tree(
    file_path: Path,
    *,
    tree_path: str,
    size: int,
    modified: str | None,
) -> dict:
    """Parse one HTML file into an ``html`` wrapper with a ``dom`` subtree."""
    text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    return html_node(tree_path, size, modified, dom=_root_dom(soup))
