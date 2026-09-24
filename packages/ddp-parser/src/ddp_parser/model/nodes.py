"""Node kinds and node classes: container, folder, file, media, unmatched, data.

Spec: sections 2, 3.1 and 4. Nodes are frozen ``msgspec.Struct``s forming a union tagged by
``kind``; field order is the JSON key order, and unset optional fields are omitted. ``path``
is a JSON Pointer string (see ``paths``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, ClassVar

import msgspec

from ddp_parser.model.paths import POINTER_PATTERN

type NodePath = Annotated[str, msgspec.Meta(pattern=POINTER_PATTERN)]


class Kind(StrEnum):
    CONTAINER = "container"
    FOLDER = "folder"
    FILE = "file"
    MEDIA = "media"
    UNMATCHED = "unmatched"
    DATA = "data"


class JsonType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"
    OBJECT = "object"
    ARRAY = "array"


class Shape(StrEnum):
    """Semantic shapes (spec 3.3). ``MIXED`` means no shape reached the threshold."""

    EMPTY = "empty"
    UUID = "uuid"
    EMAIL = "email"
    URL = "url"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    UNIX_TIMESTAMP = "unix_timestamp"
    NUMERIC = "numeric"
    ALPHA = "alpha"
    ALPHANUMERIC = "alphanumeric"
    TEXT = "text"
    PLAIN = "plain"
    MIXED = "mixed"


class MimeSource(StrEnum):
    """Where ``mime`` came from: the file's leading signature bytes ("magic number", e.g.
    ``PK\\x03\\x04`` for zip), or its extension when no signature matched (plain-text formats
    like JSON/CSV have none).
    """

    MAGIC = "magic"
    EXTENSION = "extension"


class UnmatchedReason(StrEnum):
    UNSUPPORTED_TYPE = "unsupported_type"
    PARSE_ERROR = "parse_error"
    TOO_LARGE = "too_large"
    IGNORED = "ignored"


class MinMax(msgspec.Struct, frozen=True):
    """``{min, max}`` for ``length`` (ints) and ``range`` (ints or floats)."""

    min: int | float
    max: int | float


class Stats(msgspec.Struct, frozen=True):
    """Observation counts (spec 3.1): ``count - present`` missing, ``null`` explicit nulls."""

    count: int
    present: int
    null: int = 0


class Samples(msgspec.Struct, frozen=True):
    values: tuple[str | int | float | bool, ...]
    redacted: bool


class CsvInfo(msgspec.Struct, frozen=True, kw_only=True):
    """The CSV dialect (spec 4.2). The row count is the file node's ``length``."""

    delimiter: str
    quotechar: str


class _NodeBase(msgspec.Struct, frozen=True, kw_only=True, omit_defaults=True, tag_field="kind"):
    name: str | None
    path: NodePath


class _FilesystemBase(_NodeBase, frozen=True, kw_only=True, omit_defaults=True):
    """Common file metadata (spec 4.1)."""

    size_bytes: int | None = None
    modified: datetime | None = None  # as stored in the zip: naive, no offset
    ext: str | None = None
    mime: str | None = None
    mime_source: MimeSource | None = None


# The schema fields of a value position (spec 3.1) are declared on both ``DataNode`` and
# ``FileNode`` (a parsed file carries its content inline). Struct classes cannot share them via
# a second base class, so keep the two blocks identical.


class DataNode(_NodeBase, frozen=True, kw_only=True, omit_defaults=True, tag="data"):
    """A value position inside parsed content."""

    kind: ClassVar[Kind] = Kind.DATA

    type: JsonType | tuple[JsonType, ...]  # a union is a sorted tuple
    shape: Shape | None = None
    format: str | None = None
    formats: dict[str, int] | None = None
    length: MinMax | None = None
    range: MinMax | None = None
    stats: Stats
    shapes: dict[Shape, int] = {}
    properties: dict[str, DataNode] | None = None
    items: DataNode | None = None
    samples: Samples | None = None


class FileNode(_FilesystemBase, frozen=True, kw_only=True, omit_defaults=True, tag="file"):
    """A successfully parsed file, its content schema inline. ``files`` is set for groups."""

    kind: ClassVar[Kind] = Kind.FILE

    encoding: str | None = None
    parser: str
    csv: CsvInfo | None = None
    wrapper: str | None = None
    files: int | None = None

    type: JsonType | tuple[JsonType, ...]
    shape: Shape | None = None
    format: str | None = None
    formats: dict[str, int] | None = None
    length: MinMax | None = None
    range: MinMax | None = None
    stats: Stats
    shapes: dict[Shape, int] = {}
    properties: dict[str, DataNode] | None = None
    items: DataNode | None = None
    samples: Samples | None = None


class ContainerNode(
    _FilesystemBase, frozen=True, kw_only=True, omit_defaults=True, tag="container"
):
    """A zip archive, top level or nested."""

    kind: ClassVar[Kind] = Kind.CONTAINER

    children: tuple[FilesystemNode, ...] = ()


class FolderNode(_FilesystemBase, frozen=True, kw_only=True, omit_defaults=True, tag="folder"):
    """A directory. ``folders`` is set when look-alike sibling folders were collapsed into this
    one (path segment ``{*}``, ``name`` a masked form of their names; spec 3.5).
    """

    kind: ClassVar[Kind] = Kind.FOLDER

    folders: int | None = None
    children: tuple[FilesystemNode, ...] = ()


class MediaNode(_FilesystemBase, frozen=True, kw_only=True, omit_defaults=True, tag="media"):
    kind: ClassVar[Kind] = Kind.MEDIA

    files: int | None = None


class UnmatchedNode(
    _FilesystemBase, frozen=True, kw_only=True, omit_defaults=True, tag="unmatched"
):
    kind: ClassVar[Kind] = Kind.UNMATCHED

    reason: UnmatchedReason
    error: str | None = None
    files: int | None = None


type FilesystemNode = ContainerNode | FolderNode | FileNode | MediaNode | UnmatchedNode
type Node = FilesystemNode | DataNode
