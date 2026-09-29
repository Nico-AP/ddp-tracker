"""Redact identifying path / folder / key segments (emails, FB thread keys, …)."""

from __future__ import annotations

import hashlib

from ddp_parser.model.paths import ITEMS, ROOT, join, split
from ddp_parser.privacy import path_patterns as patterns

COLLAPSED = "{*}"
RESERVED_SEGMENTS = frozenset({ITEMS, COLLAPSED})


def redact_fb_thread_key(segment: str) -> str | None:
    """Replace FB inbox thread folder names; keep group size, hide user/id."""
    match = patterns.FB_THREAD_KEY.match(segment)
    if match is None:
        return None
    digest = hashlib.sha256(segment.encode("utf-8")).hexdigest()
    user_fill = "u" + digest[:8]
    id_fill = digest[8:24]
    others = match.group("others")
    if others is not None:
        return f"{user_fill}and{others}others_{id_fill}"
    return f"{user_fill}_{id_fill}"


def _under_messages(parent_parts: tuple[str, ...] | list[str]) -> bool:
    return any(part.lower() == patterns.MESSAGES_ANCESTOR for part in parent_parts)


def redact_path_segment(  # noqa: PLR0911 — ported rule chain from ddp2json
    segment: str,
    parent_parts: tuple[str, ...] | list[str] = (),
) -> str:
    """Replace a path segment that looks identifying."""
    if segment in RESERVED_SEGMENTS or "{n}" in segment:
        return segment
    stripped = segment.strip()
    if not stripped:
        return segment

    if _under_messages(parent_parts):
        fb = redact_fb_thread_key(stripped)
        if fb is not None:
            return fb

    if patterns.EMAIL.match(stripped):
        return "{email}"
    if patterns.UUID.match(stripped):
        return "{uuid}"
    if patterns.PHONE_ISH.match(stripped) and sum(char.isdigit() for char in stripped) >= 7:  # noqa: PLR2004
        return "{phone}"
    if patterns.LONG_HEX.match(stripped):
        return "{hex_id}"
    if patterns.NUMERIC_ID.match(stripped):
        return "{numeric_id}"
    return segment


def redact_path_parts(parts: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Redact each path part with awareness of ancestors (e.g. messages/)."""
    out: list[str] = []
    for part in parts:
        out.append(redact_path_segment(part, tuple(out)))
    return tuple(out)


def redact_path(path: str) -> str:
    """Redact every segment of a JSON Pointer path."""
    if path == ROOT:
        return ROOT
    return _join_parts(redact_path_parts(split(path)))


def join_redacted(parent: str, segment: str) -> str:
    """Append ``segment`` to ``parent``, redacting ``segment`` in context."""
    ancestors = split(parent)
    return join(parent, redact_path_segment(segment, ancestors))


def _join_parts(parts: tuple[str, ...]) -> str:
    path = ROOT
    for part in parts:
        path = join(path, part)
    return path
