"""Redact full content trees to descriptor schemas (no raw values).

Owns privacy scrubbing when enabled: identifying path/key segments via
``path_redact``, and data values via ``describe``.
"""

from __future__ import annotations

from ..tree.nodes import is_file_ref, is_leaf, is_list
from .describe import describe_value
from .path_redact import redact_path_parts, redact_path_segment


def _schema_file_ref(leaf: dict, *, redact_paths: bool) -> dict:
    """Keep media/unmatched metadata; optionally scrub identifying path segments."""
    path = leaf.get("path") or ""
    if redact_paths:
        path = "/".join(redact_path_parts(path.split("/")))
    return {
        "kind": leaf.get("kind"),
        "path": path,
        "size": leaf.get("size"),
        "modified": leaf.get("modified"),
        "ext": leaf.get("ext"),
        "mime": leaf.get("mime"),
    }


def redact_tree(
    node,
    field_path: tuple[str, ...] = (),
    *,
    values_mode: str = "none",
    redact_paths: bool = True,
):
    """Deep-copy tree: data → descriptors; optionally scrub PII in keys/paths.

    ``field_path`` tracks ancestor keys so blocked fields never keep
    ``values`` enums in ``safe`` mode (uses original keys; emitted keys may
    be redacted when ``redact_paths`` is True).

    ``values_mode`` is ``none``, ``safe``, or ``all`` (see ``describe_value``).
    """
    if not isinstance(node, dict):
        return node

    if is_leaf(node):
        if node.get("kind") == "data":
            return describe_value(
                node.get("value"),
                field_path=field_path,
                values_mode=values_mode,
            )
        if is_file_ref(node):
            return _schema_file_ref(node, redact_paths=redact_paths)
        return node

    if is_list(node):
        items = node.get("items") or {}
        return {
            "kind": "list",
            "items": {
                str(k): redact_tree(
                    v,
                    field_path + (str(k),),
                    values_mode=values_mode,
                    redact_paths=redact_paths,
                )
                for k, v in items.items()
            },
        }

    out: dict = {}
    for key, child in node.items():
        key_s = str(key)
        out_key = redact_path_segment(key_s, field_path) if redact_paths else key_s
        out[out_key] = redact_tree(
            child,
            field_path + (key_s,),
            values_mode=values_mode,
            redact_paths=redact_paths,
        )
    return out


def path_template(path: str) -> str:
    """Collapse list indices and obvious PII segments into a stable template."""
    raw = path.split("/")
    redacted = redact_path_parts(raw)
    parts = []
    for part in redacted:
        if part.isdigit():
            parts.append("{n}")
        else:
            parts.append(part)
    return "/".join(parts)
