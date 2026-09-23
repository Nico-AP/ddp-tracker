from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field


class NodeType(enum.StrEnum):
    DIRECTORY = "dir"
    FILE = "file"
    OBJECT = "object"
    ARRAY = "array"
    FIELD = "field"
    SCALAR = "scalar"


class DataType(enum.StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SchemaNode:
    name: str
    node_type: NodeType
    data_type: DataType = DataType.UNKNOWN
    is_optional: bool = False
    children: tuple[SchemaNode, ...] = field(default_factory=tuple)
    example_values: tuple[str, ...] = field(default_factory=tuple)  # raw, pre-anonymization

    def with_children(self, children: tuple[SchemaNode, ...]) -> SchemaNode:
        # dataclasses are frozen so children get merged via reconstruction, not mutation
        return dataclasses.replace(self, children=children)


@dataclass(frozen=True)
class Schema:
    root_nodes: tuple[SchemaNode, ...]
    fingerprint: str
