"""Rewrite stored schema documents so every node path is redacted."""

from __future__ import annotations

from typing import Any

from ddp_parser.privacy.path_redact import redact_path


def redact_document_paths(document: dict[str, Any]) -> None:
    """Update paths on the root tree and in warnings, in place."""
    pending = [document["root"]]
    while pending:
        node = pending.pop()
        if path := node.get("path"):
            node["path"] = redact_path(path)
        pending.extend(node.get("children") or [])
        pending.extend((node.get("properties") or {}).values())
        if items := node.get("items"):
            pending.append(items)
    for warning in document.get("warnings") or ():
        if path := warning.get("path"):
            warning["path"] = redact_path(path)
