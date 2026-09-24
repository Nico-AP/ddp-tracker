"""The document envelope: ``spec_version``, ``parser_version``, ``created_at``, ``source``,
``options``, ``warnings`` and ``root``.
"""

from __future__ import annotations

from datetime import datetime

import msgspec

from ddp_parser.model.nodes import FilesystemNode, NodePath

SPEC_VERSION = "1.0"

type OptionValue = str | int | float | bool | list[str] | None


class Source(msgspec.Struct, frozen=True):
    """The input as a whole: its file name, size and content hash."""

    name: str | None
    size_bytes: int
    sha256: str


class ParseWarning(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True):
    """A document-level warning, e.g. ``ambiguous_date_order`` or ``path_traversal``.

    ``path`` points at the affected node when there is one.
    """

    code: str
    message: str | None = None
    path: NodePath | None = None


class Document(msgspec.Struct, frozen=True, kw_only=True):
    spec_version: str = SPEC_VERSION
    parser_version: str
    created_at: datetime
    source: Source
    options: dict[str, OptionValue] = {}
    warnings: tuple[ParseWarning, ...] = ()
    root: FilesystemNode
