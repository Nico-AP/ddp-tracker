"""Classify a single scalar into a shape. Ordered checks, first match wins.

Spec: section 3.3 *Shapes*. Returns the shape plus the set of ``format`` candidates the value
fits (date patterns or a unix unit); the set is empty for shapes without a format.
"""

import re

from ddp_parser.model import Shape
from ddp_parser.schematize.date_formats import match_formats

type Classified = tuple[Shape, frozenset[str]]

_NO_FORMAT: frozenset[str] = frozenset()

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://\S+$")
_DIGITS = re.compile(r"^\d+$")
_NUMERIC = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_CAMEL_ID = re.compile(r"[a-z0-9]Id$")
_MAX_UNIX_DIGITS = 17  # microsecond timestamps before 2100 have 16 digits

# Plausible unix timestamps: 1990-01-01 <= t < 2100-01-01, per unit. The ranges don't overlap.
_UNIX_S = (631_152_000, 4_102_444_800)
_UNIX_RANGES = (
    ("s", _UNIX_S[0], _UNIX_S[1]),
    ("ms", _UNIX_S[0] * 1_000, _UNIX_S[1] * 1_000),
    ("us", _UNIX_S[0] * 1_000_000, _UNIX_S[1] * 1_000_000),
)


def is_id_key(name: str | None) -> bool:
    """Keys like ``id``, ``user_id`` or ``userId`` never hold unix timestamps (spec 3.3)."""
    if name is None:
        return False
    lower = name.lower()
    return lower == "id" or lower.endswith("_id") or bool(_CAMEL_ID.search(name))


def unix_unit(value: float) -> str | None:
    for unit, low, high in _UNIX_RANGES:
        if low <= value < high:
            return unit
    return None


def classify_number(value: float, *, id_key: bool) -> Classified:
    unit = None if id_key else unix_unit(value)
    if unit is not None:
        return Shape.UNIX_TIMESTAMP, frozenset({unit})
    return Shape.PLAIN, _NO_FORMAT


def classify_string(value: str, *, id_key: bool) -> Classified:  # noqa: PLR0911 - one return per shape, in spec order
    text = value.strip()
    if not text:
        return Shape.EMPTY, _NO_FORMAT
    if _UUID.match(text):
        return Shape.UUID, _NO_FORMAT
    if _EMAIL.match(text):
        return Shape.EMAIL, _NO_FORMAT
    if _URL.match(text):
        return Shape.URL, _NO_FORMAT
    date = match_formats(text)
    if date is not None:
        return date
    if (
        _DIGITS.match(text)
        and len(text) <= _MAX_UNIX_DIGITS
        and not id_key
        and (unit := unix_unit(int(text))) is not None
    ):
        return Shape.UNIX_TIMESTAMP, frozenset({unit})
    if _NUMERIC.match(text):
        return Shape.NUMERIC, _NO_FORMAT
    if text.isalpha():
        return Shape.ALPHA, _NO_FORMAT
    if text.isalnum():
        return Shape.ALPHANUMERIC, _NO_FORMAT
    return Shape.TEXT, _NO_FORMAT
