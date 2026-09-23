"""Node constructors and the archive content-tree contract.

Tree nodes are plain dicts with the following shapes:

Leaves
  - Data:  ``{"kind": "data", "value": ...}``
    In schema mode, ``value`` is replaced by ``type`` / ``shape`` / optional
    ``length`` / ``format`` (strftime or ``s``/``ms`` for timestamps).
    ``--enums`` may add short non-PII ``values``; ``--schema-full``
    keeps every scalar under ``values`` without path scrubbing.
    Optional ``taxonomy`` on a leaf is an in-memory fused view only
    (``apply_overlay``). Persisted reports keep mapping in a sidecar overlay.
  - Media: ``{"kind": "media", "path", "size", "modified", "ext", "mime"}``
    Image / video / audio (and a few related) binaries only.
  - Unmatched: same metadata fields as media, ``kind: "unmatched"``.
    Used when a file is not parsed / not projected (failed parse, HTML with
    no matching spec, or a non-media unknown type).

Collections
  - List:  ``{"kind": "list", "items": {"0": ..., "1": ..., ...}}``
    After schema summarization: ``{"kind": "list", "length", "item": ...}``.
  - Variants (schema only): ``{"kind": "variants", "options": [...]}``

HTML (content-tree only, before schema projection)
  - ``{"kind": "html", "path", "size", "modified", "ext", "mime", "dom": ...}``
    ``dom`` encodes elements as plain objects with string ``tag`` / ``attrs``
    (attrs omitted when empty) and a ``children`` list of elements or data
    leaves. Schema modes project via ``engine.schema.html`` + ``policy/html``
    specs, or strip to an unmatched leaf when no spec matches.

Directories and JSON objects are plain dicts (no ``kind`` key). An optional
``optional: True`` flag may appear on schema nodes for fields missing from
some list items.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

# MIME prefixes treated as real media (not "unmatched").
_MEDIA_MIME_PREFIXES = ("image/", "video/", "audio/")
_MEDIA_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".svg",
        ".mp4",
        ".m4v",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".3gp",
        ".mp3",
        ".m4a",
        ".aac",
        ".wav",
        ".ogg",
        ".flac",
        ".opus",
    }
)


def data_leaf(value) -> dict:
    """A scalar key-value leaf."""
    return {"kind": "data", "value": value}


def _file_meta(path: str, size: int, modified: str | None) -> dict:
    ext = Path(path).suffix.lower() or None
    mime, _ = mimetypes.guess_type(path)
    return {
        "path": path,
        "size": size,
        "modified": modified,
        "ext": ext,
        "mime": mime,
    }


def is_media_path(path: str) -> bool:
    """True if ``path`` looks like image / video / audio."""
    ext = Path(path).suffix.lower()
    if ext in _MEDIA_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith(_MEDIA_MIME_PREFIXES):
        return True
    return False


def media_leaf(path: str, size: int, modified: str | None) -> dict:
    """An image / video / audio file leaf (path reference + metadata)."""
    return {"kind": "media", **_file_meta(path, size, modified)}


def unmatched_leaf(path: str, size: int, modified: str | None) -> dict:
    """A file that was not parsed or not matched by a projection spec."""
    return {"kind": "unmatched", **_file_meta(path, size, modified)}


def file_leaf(path: str, size: int, modified: str | None) -> dict:
    """Media leaf for image/video/audio; otherwise unmatched."""
    if is_media_path(path):
        return media_leaf(path, size, modified)
    return unmatched_leaf(path, size, modified)


def html_node(
    path: str,
    size: int,
    modified: str | None,
    dom: dict | None = None,
) -> dict:
    """An HTML file wrapper: media metadata plus a parsed DOM subtree."""
    meta = _file_meta(path, size, modified)
    return {
        "kind": "html",
        **meta,
        "mime": meta["mime"] or "text/html",
        "dom": dom if dom is not None else {},
    }


def list_node(items: dict | None = None) -> dict:
    """A sequenced collection (JSON array or CSV column rows)."""
    return {"kind": "list", "items": items if items is not None else {}}


def is_leaf(node) -> bool:
    """True if node is a data, media, or unmatched leaf dict."""
    return isinstance(node, dict) and node.get("kind") in (
        "data",
        "media",
        "unmatched",
    )


def is_list(node) -> bool:
    """True if node is an explicit list wrapper."""
    return isinstance(node, dict) and node.get("kind") == "list"


def is_html(node) -> bool:
    """True if node is an HTML wrapper with a DOM subtree."""
    return isinstance(node, dict) and node.get("kind") == "html"


def is_file_ref(node) -> bool:
    """True if node is a media or unmatched path reference leaf."""
    return isinstance(node, dict) and node.get("kind") in ("media", "unmatched")
