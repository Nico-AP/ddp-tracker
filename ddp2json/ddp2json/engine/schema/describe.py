"""Classify scalar values into structural descriptors (no raw content).

``values_mode`` controls whether descriptors include a ``values`` list:
``none`` (never), ``safe`` (short non-PII enums), or ``all`` (every scalar).
In ``safe`` mode, merging unions enums and drops them past
``MAX_ENUM_VALUES`` (from ``policy.scrub.fields``).
"""

from __future__ import annotations

import re
from datetime import datetime

from ...policy.empty import is_empty_section_message
from ...policy.scrub.fields import (
    AD_PREFERENCES_BLOCKED_CHILD,
    AD_PREFERENCES_FILENAMES,
    BLOCKED_VALUE_FIELD_PREFIXES,
    BLOCKED_VALUE_FIELD_SUFFIXES,
    BLOCKED_VALUE_FIELDS_EXACT,
    MAX_ENUM_VALUES,
    MAX_PRESERVE_LEN,
    NAME_KEY_ALLOW,
    SENSITIVE_SHAPES,
)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^(https?|ftp)://|^www\.", re.I)
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_HEX = re.compile(r"^[0-9a-f]+$", re.I)
_DIGITS = re.compile(r"^\d+$")
_PHONE = re.compile(r"^\+?[\d\s().-]{7,}$")
_ALPHA = re.compile(r"^[\W_]*[^\W\d_]+(?:[\s'\-.][^\W\d_]+)*[\W_]*$", re.UNICODE)
_ALNUM = re.compile(r"^[0-9A-Za-z]+$")
_ISO_DT = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)
_COMMON_DT = re.compile(
    r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T]\d{1,2}:\d{2}(:\d{2})?)?$"
)
# Decimal / measurement strings (watch position, scores, …) — not enums.
_DECIMAL = re.compile(r"^[+-]?\d+\.\d+$")
_IPV4 = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
# Field / enum keys: foo_bar, FooBar, FOO_BAR, foo-bar, true/false-ish tokens.
_KEY_LIKE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-./:]*$")

# (shape, strftime) tried in order for date / datetime strings.
_DATE_FORMATS: tuple[tuple[str, str], ...] = (
    ("datetime", "%Y-%m-%dT%H:%M:%S.%fZ"),
    ("datetime", "%Y-%m-%dT%H:%M:%SZ"),
    ("datetime", "%Y-%m-%dT%H:%M:%S.%f"),
    ("datetime", "%Y-%m-%dT%H:%M:%S"),
    ("datetime", "%Y-%m-%d %H:%M:%S"),
    ("date", "%Y-%m-%d"),
    ("date", "%b %d, %Y"),  # Jan 10, 2024
    ("date", "%B %d, %Y"),  # January 10, 2024
    ("date", "%d %b %Y"),  # 10 Jan 2024
    ("date", "%d %B %Y"),  # 10 January 2024
    ("date", "%b %d %Y"),
    ("date", "%B %d %Y"),
    ("date", "%m/%d/%Y"),
    ("date", "%d.%m.%Y"),
)


def _normalize_field_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(key).strip().lower()).strip("_")


def is_blocked_value_field(key: str) -> bool:
    """True if a JSON key / group title must not expose enum ``values``."""
    k = _normalize_field_key(key)
    if not k:
        return False
    if k in BLOCKED_VALUE_FIELDS_EXACT:
        return True
    if k in NAME_KEY_ALLOW or k.endswith(tuple(NAME_KEY_ALLOW)):
        return False
    if k.endswith(BLOCKED_VALUE_FIELD_SUFFIXES) or k.startswith(
        BLOCKED_VALUE_FIELD_PREFIXES
    ):
        return True
    # sender_name, full_name, home_city, current_city, …
    if k.endswith("_name") or k.startswith("name_"):
        return True
    if k.endswith("_city") or k.startswith("city_"):
        return True
    if k.endswith("_town") or k.startswith("town_"):
        return True
    if k.endswith("_actor") or k.startswith("actor_"):
        return True
    if k.endswith("_author") or k.startswith("author_"):
        return True
    return False


def path_blocks_enum_values(field_path: tuple[str, ...] | list[str] | None) -> bool:
    """True if any path segment blocks preserving ``values``."""
    if not field_path:
        return False
    if any(is_blocked_value_field(part) for part in field_path):
        return True

    # Ad preference label catalogues are identifying; keep shape only.
    parts_l = [str(p).lower() for p in field_path]
    under_ad_prefs = any(
        p in AD_PREFERENCES_FILENAMES
        or any(p.endswith("/" + name) for name in AD_PREFERENCES_FILENAMES)
        for p in parts_l
    )
    if under_ad_prefs and any(p == AD_PREFERENCES_BLOCKED_CHILD for p in parts_l):
        return True
    return False


def path_implies_cookie(field_path: tuple[str, ...] | list[str] | None) -> bool:
    """True if any path segment suggests cookie-related PII (force shape)."""
    if not field_path:
        return False
    for part in field_path:
        k = _normalize_field_key(part)
        if k in {"cookie", "cookies"} or k.endswith(("_cookie", "_cookies")):
            return True
        if k.startswith(("cookie_", "cookies_")):
            return True
    return False


def _looks_like_ipv4(s: str) -> bool:
    if not _IPV4.match(s):
        return False
    return all(0 <= int(p) <= 255 for p in s.split("."))


def _looks_like_ipv6(s: str) -> bool:
    if ":" not in s or "." in s.split("%")[0]:
        # allow IPv4-mapped later; keep simple for now
        if "." in s:
            return False
    core = s.split("%")[0]  # drop zone id
    if core.count(":") < 2:
        return False
    if not re.fullmatch(r"[0-9a-f:]+", core, re.I):
        return False
    # Reject pure timestamps / ratios mistaken for ipv6
    parts = core.split(":")
    if len(parts) > 8:
        return False
    return all(len(p) <= 4 for p in parts)


def _normalize_for_strptime(s: str) -> str:
    """Strip common ISO offset forms so listed formats can match."""
    if s.endswith("+00:00") or s.endswith("-00:00"):
        return s[:-6]
    return s


def _match_date_format(s: str) -> tuple[str, str] | None:
    """Return (shape, strftime) if ``s`` parses as a known date/datetime."""
    candidate = _normalize_for_strptime(s)
    for shape, fmt in _DATE_FORMATS:
        try:
            datetime.strptime(candidate, fmt)
            return shape, fmt
        except ValueError:
            continue
    return None


def _unix_format(digits: str) -> str | None:
    """Return ``s`` / ``ms`` for plausible unix timestamps, else None."""
    if not digits.isdigit():
        return None
    n = int(digits)
    if len(digits) == 10 and 1_000_000_000 <= n < 10_000_000_000:
        return "s"
    if len(digits) == 13 and 1_000_000_000_000 <= n < 10_000_000_000_000:
        return "ms"
    return None


def _looks_like_unix(digits: str) -> bool:
    """True for 10-digit seconds or 13-digit millisecond unix timestamps."""
    return _unix_format(digits) is not None


def _classify_string(text: str) -> tuple[str, str | None]:
    """Classify a string into (shape, optional format)."""
    s = text.strip()
    if not s or is_empty_section_message(s):
        return "empty", None
    if _EMAIL.match(s):
        return "email", None
    if _looks_like_ipv4(s) or _looks_like_ipv6(s):
        return "ip_address", None
    if _URL.match(s):
        return "url", None
    if _UUID.match(s):
        return "uuid", None

    matched = _match_date_format(s)
    if matched is not None:
        return matched
    # Loose date/datetime regex hit without a concrete strptime format.
    if _ISO_DT.match(s) or _COMMON_DT.match(s):
        return ("datetime" if ":" in s or "T" in s else "date"), None

    if _DECIMAL.match(s):
        return "decimal", None
    if _DIGITS.match(s):
        unix_fmt = _unix_format(s)
        if unix_fmt is not None:
            return "unix_timestamp", unix_fmt
        return "digits", None
    if _PHONE.match(s) and sum(c.isdigit() for c in s) >= 7:
        return "phone", None
    if _HEX.match(s) and len(s) >= 8 and any(c.isalpha() for c in s):
        return "hex", None
    if s.isalpha():
        return "alpha", None
    if _ALNUM.match(s):
        return "alphanumeric", None
    if _ALPHA.match(s) and any(c.isalpha() for c in s):
        if any(c.isspace() for c in s):
            return "text", None
        return "alpha", None
    if any(c.isspace() for c in s) or len(s) > 32:
        return "text", None
    return "other", None


def _string_shape(text: str) -> str:
    """Classify a string into a structural shape label (email, url, text, …)."""
    return _classify_string(text)[0]


def is_preservable_value(
    value,
    shape: str | None = None,
    field_path: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True if ``value`` may appear in a schema ``values`` enum list."""
    if path_blocks_enum_values(field_path):
        return False
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        if shape == "unix_timestamp" or _looks_like_unix(str(abs(value))):
            return False
        # Only binary flags (0/1); other integers are opaque ids / counts.
        return value in (0, 1)
    if isinstance(value, float):
        if shape == "unix_timestamp":
            return False
        return value in (0.0, 1.0)
    if not isinstance(value, str):
        return False

    if shape is None:
        shape = _string_shape(value)
    if shape in SENSITIVE_SHAPES:
        return False
    if len(value) > MAX_PRESERVE_LEN or "\n" in value or "\r" in value:
        return False

    s = value.strip()
    if not s:
        return True

    # Digit strings: only binary "0"/"1", not opaque numeric ids.
    if shape == "digits" or _DIGITS.match(s):
        return s in ("0", "1")

    # Identifier / enum keys (ent_field_name, setting flags, …).
    if _KEY_LIKE.match(s) and " " not in s:
        return True

    # Short UI labels / repeated tokens (few words, not prose).
    words = s.split()
    if len(words) <= 6 and len(s) <= 64:
        return True

    return False


def merge_enum_values(
    a,
    b,
    field_path: tuple[str, ...] | list[str] | None = None,
    *,
    values_mode: str = "safe",
):
    """Union two ``values`` lists; return None if too large or unsafe.

    ``values_mode``:
      - ``none``: always drop
      - ``safe``: only preservable non-PII values; drop past ``MAX_ENUM_VALUES``
      - ``all``: keep every distinct value (no PII filter / cardinality cap)
    """
    if values_mode == "none":
        return None
    if values_mode == "all":
        combined: list = []
        seen: set = set()
        for v in list(a or []) + list(b or []):
            try:
                key = v
                hash(key)
            except TypeError:
                key = repr(v)
            if key in seen:
                continue
            seen.add(key)
            combined.append(v)
        return combined or None

    if path_blocks_enum_values(field_path):
        return None
    combined = []
    seen = set()
    for v in list(a or []) + list(b or []):
        if not is_preservable_value(v, field_path=field_path):
            return None
        try:
            key = v
            hash(key)
        except TypeError:
            key = repr(v)
        if key in seen:
            continue
        seen.add(key)
        combined.append(v)
        if len(combined) > MAX_ENUM_VALUES:
            return None
    return combined or None


def describe_value(
    value,
    field_path: tuple[str, ...] | list[str] | None = None,
    *,
    values_mode: str = "none",
) -> dict:
    """Return a data leaf descriptor: type + shape (+ length, format, values).

    ``values_mode``:
      - ``none``: structural descriptors only
      - ``safe``: short non-PII enums (blocked-field / shape rules apply)
      - ``all``: always attach the raw value under ``values``

    Date / datetime / unix leaves may include ``format`` (strftime, or
    ``s`` / ``ms`` for unix timestamps) when a concrete pattern is known.
    """

    def _keep(shape: str | None) -> bool:
        if values_mode == "none":
            return False
        if values_mode == "all":
            return True
        return is_preservable_value(value, shape, field_path)

    if value is None:
        out = {"kind": "data", "type": "null", "shape": "null"}
        if _keep("null"):
            out["values"] = [None]
        return out
    if isinstance(value, bool):
        out = {"kind": "data", "type": "boolean", "shape": "boolean"}
        if _keep("boolean"):
            out["values"] = [value]
        return out
    if isinstance(value, int) and not isinstance(value, bool):
        digits = str(abs(value))
        unix_fmt = _unix_format(digits)
        if unix_fmt is not None:
            out = {
                "kind": "data",
                "type": "integer",
                "shape": "unix_timestamp",
                "format": unix_fmt,
            }
            if _keep("unix_timestamp"):
                out["values"] = [value]
            return out
        out = {"kind": "data", "type": "integer", "shape": "integer"}
        if _keep("integer"):
            out["values"] = [value]
        return out
    if isinstance(value, float):
        if value.is_integer():
            unix_fmt = _unix_format(str(abs(int(value))))
            if unix_fmt is not None:
                out = {
                    "kind": "data",
                    "type": "number",
                    "shape": "unix_timestamp",
                    "format": unix_fmt,
                }
                if _keep("unix_timestamp"):
                    out["values"] = [value]
                return out
        out = {"kind": "data", "type": "number", "shape": "number"}
        if _keep("number"):
            out["values"] = [value]
        return out
    if isinstance(value, str):
        shape, fmt = _classify_string(value)
        if path_implies_cookie(field_path):
            shape = "cookie"
            fmt = None
        # Empty-section stubs are structural emptiness, not measured text.
        length = 0 if shape == "empty" else len(value)
        out = {
            "kind": "data",
            "type": "string",
            "shape": shape,
            "length": length,
        }
        if fmt is not None:
            out["format"] = fmt
        if _keep(shape):
            out["values"] = [value]
        return out
    return {
        "kind": "data",
        "type": type(value).__name__,
        "shape": "other",
    }
