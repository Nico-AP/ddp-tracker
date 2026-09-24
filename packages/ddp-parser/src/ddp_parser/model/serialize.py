"""Conversion between the model and JSON / plain Python data.

msgspec derives the format from the Struct definitions in ``nodes`` and ``document``, including
validation on the way in. ``to_dict`` / ``from_dict`` target plain JSON-compatible data, e.g.
for a database JSON column.
"""

from typing import Any

import msgspec

from ddp_parser.errors import InvalidDocumentError
from ddp_parser.model.document import Document


def to_json(document: Document, *, indent: int = 2) -> str:
    encoded = msgspec.json.encode(document)
    return msgspec.json.format(encoded, indent=indent).decode()


def from_json(text: str | bytes) -> Document:
    try:
        return msgspec.json.decode(text, type=Document)
    except msgspec.DecodeError as exc:  # ValidationError is a subclass
        msg = f"invalid schema document: {exc}"
        raise InvalidDocumentError(msg) from exc


def to_dict(document: Document) -> dict[str, Any]:
    """Plain JSON data (dicts, lists, str, numbers, bool, None), as ``json.loads`` would give."""
    data: dict[str, Any] = msgspec.json.decode(msgspec.json.encode(document))
    return data


def from_dict(data: dict[str, Any]) -> Document:
    try:
        return msgspec.convert(data, type=Document)
    except msgspec.ValidationError as exc:
        msg = f"invalid schema document: {exc}"
        raise InvalidDocumentError(msg) from exc
