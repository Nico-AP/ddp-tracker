"""The output contract: pure data classes, no I/O.

This is what downstream consumers (e.g. the Django app) depend on.
"""

from ddp_parser.model.document import SPEC_VERSION, Document, ParseWarning, Source
from ddp_parser.model.nodes import (
    ContainerNode,
    CsvInfo,
    DataNode,
    FileNode,
    FilesystemNode,
    FolderNode,
    JsonType,
    Kind,
    MediaNode,
    MimeSource,
    MinMax,
    Node,
    Samples,
    Shape,
    Stats,
    UnmatchedNode,
    UnmatchedReason,
)
from ddp_parser.model.serialize import from_dict, from_json, to_dict, to_json

__all__ = [
    "SPEC_VERSION",
    "ContainerNode",
    "CsvInfo",
    "DataNode",
    "Document",
    "FileNode",
    "FilesystemNode",
    "FolderNode",
    "JsonType",
    "Kind",
    "MediaNode",
    "MimeSource",
    "MinMax",
    "Node",
    "ParseWarning",
    "Samples",
    "Shape",
    "Source",
    "Stats",
    "UnmatchedNode",
    "UnmatchedReason",
    "from_dict",
    "from_json",
    "to_dict",
    "to_json",
]
