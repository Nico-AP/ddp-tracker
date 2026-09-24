"""Date / datetime / time format detection.

Every value is checked against a grid of strptime candidates (date part x separator x time
part x zone). A value's *signature* (digits replaced by ``9``) decides which candidates are
structurally possible, and is cached; ``strptime`` then confirms each one for the actual value.
A value may fit several candidates (``01/02/2026``); ``resolve_format`` intersects the sets
across all values of a node (spec 3.3, ambiguous dates).

Fractional seconds are reported as ``%<n>f`` (e.g. ``%3f``); ``to_strptime`` turns such a
format back into one ``datetime.strptime`` accepts.
"""

import re
from collections import Counter
from datetime import datetime
from itertools import product

from ddp_parser.model import Shape

_DATE_PARTS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%a, %d %b %Y",
)
_TIME_PARTS = ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f", "%I:%M %p", "%I:%M:%S %p")
_SEPARATORS = ("T", " ", ", ")
_ZONES = ("", "Z", "%z", " %z")

# Candidates in priority order; the first one is preferred when several fit.
_CANDIDATES: tuple[tuple[Shape, str], ...] = (
    *(
        (Shape.DATETIME, d + s + t + z)
        for d, s, t, z in product(_DATE_PARTS, _SEPARATORS, _TIME_PARTS, _ZONES)
    ),
    *((Shape.DATE, d) for d in _DATE_PARTS),
    *((Shape.TIME, t) for t in _TIME_PARTS),
)

_TOKEN_REGEX = {
    "%Y": r"\d{4}",
    "%m": r"\d{1,2}",
    "%d": r"\d{1,2}",
    "%H": r"\d{1,2}",
    "%I": r"\d{1,2}",
    "%M": r"\d{2}",
    "%S": r"\d{2}",
    "%f": r"(?P<f>\d{1,6})",
    "%p": r"[AaPp][Mm]",
    "%z": r"[+-]\d{2}:?\d{2}",
    "%b": r"[A-Za-z]{3}",
    "%B": r"[A-Za-z]{4,}",
    "%a": r"[A-Za-z]{3}",
}
_TOKEN = re.compile(r"%[A-Za-z]")
_FRACTION = re.compile(r"%(\d)f")

# Cheap pre-filter: short, starts with a digit or letter, only date-ish characters.
_MAX_LENGTH = 40
_MIN_DIGITS = 3
_PLAUSIBLE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z :.,/+\-]*$")


def _to_regex(fmt: str) -> re.Pattern[str]:
    parts: list[str] = []
    last = 0
    for token in _TOKEN.finditer(fmt):
        parts.append(re.escape(fmt[last : token.start()]))
        parts.append(_TOKEN_REGEX[token.group()])
        last = token.end()
    parts.append(re.escape(fmt[last:]))
    return re.compile("^" + "".join(parts) + "$")


_COMPILED = tuple((shape, fmt, _to_regex(fmt)) for shape, fmt in _CANDIDATES)


type _Structural = tuple[tuple[Shape, str, str], ...]

# Candidate regexes only look at digit positions and the exact other characters, so all values
# with the same signature share one result.
_CACHE_SIZE = 4096
_cache: dict[str, _Structural] = {}


def _structural_candidates(value: str) -> _Structural:
    """Candidates whose regex fits ``value``: (shape, reported format, strptime format)."""
    signature = re.sub(r"\d", "9", value)
    cached = _cache.get(signature)
    if cached is not None:
        return cached
    found: list[tuple[Shape, str, str]] = []
    for shape, fmt, regex in _COMPILED:
        match = regex.match(value)
        if match is None:
            continue
        digits = match.groupdict().get("f")
        report = fmt.replace("%f", f"%{len(digits)}f") if digits else fmt
        found.append((shape, report, fmt))
    if len(_cache) >= _CACHE_SIZE:
        _cache.clear()
    _cache[signature] = result = tuple(found)
    return result


def match_formats(value: str) -> tuple[Shape, frozenset[str]] | None:
    """Shape and every candidate format ``value`` parses under, or None if it is no date/time."""
    if (
        len(value) > _MAX_LENGTH
        or sum(char.isdigit() for char in value) < _MIN_DIGITS
        or not _PLAUSIBLE.match(value)
    ):
        return None
    shape: Shape | None = None
    formats: set[str] = set()
    for candidate_shape, report, parse in _structural_candidates(value):
        try:
            datetime.strptime(value, parse)  # noqa: DTZ007 - validation only, the result is unused
        except ValueError:
            continue
        shape = shape or candidate_shape
        formats.add(report)
    return None if shape is None else (shape, frozenset(formats))


def to_strptime(fmt: str) -> str:
    """Turn a reported format (``%3f``) back into a strptime format (``%f``)."""
    return _FRACTION.sub("%f", fmt)


def resolve_format(
    fits: Counter[frozenset[str]] | None,
) -> tuple[str | None, dict[str, int] | None, bool]:
    """Decide a node's ``format`` from how many values fit which set of formats.

    Returns ``(format, formats, ambiguous)``: one format if every value fits it; otherwise no
    format and ``formats`` counts. ``ambiguous`` is True when several formats fit *all* values
    (e.g. ``%d/%m/%Y`` and ``%m/%d/%Y``), which the spec reports as a warning.
    """
    if not fits:
        return None, None, False
    common = frozenset.intersection(*fits)
    if len(common) == 1:
        return next(iter(common)), None, False
    total = sum(fits.values())
    if common:
        return None, dict.fromkeys(sorted(common), total), True
    counts: Counter[str] = Counter()
    for fitting, count in fits.items():
        counts[min(fitting)] += count
    return None, dict(sorted(counts.items())), False
