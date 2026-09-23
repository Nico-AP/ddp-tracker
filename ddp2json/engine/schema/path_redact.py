"""Redact identifying path / folder segments (emails, FB thread keys, …).

Patterns come from ``ddp2json.policy.scrub.path_patterns``.
"""

from __future__ import annotations

import hashlib

from ...policy.scrub import path_patterns as patterns


def redact_fb_thread_key(segment: str) -> str | None:
    """Replace FB inbox thread folder names; keep group size, hide user/id.

    Examples:
      testuser1_1044559665449543250
        → u1a2b3c4_d5e6f7a8b9c0d1e2
      testuser2and129others_4876204856358246
        → u9f0e1d2and129others_a1b2c3d4e5f60718
    """
    m = patterns.FB_THREAD_KEY.match(segment)
    if not m:
        return None
    digest = hashlib.sha256(segment.encode("utf-8")).hexdigest()
    user_fill = "u" + digest[:8]
    id_fill = digest[8:24]
    others = m.group("others")
    if others is not None:
        return f"{user_fill}and{others}others_{id_fill}"
    return f"{user_fill}_{id_fill}"


def _under_messages(parent_parts: tuple[str, ...] | list[str]) -> bool:
    needle = patterns.MESSAGES_ANCESTOR
    return any(p.lower() == needle for p in parent_parts)


def redact_path_segment(
    segment: str,
    parent_parts: tuple[str, ...] | list[str] = (),
) -> str:
    """Replace a path/folder segment that looks identifying.

    Catches emails, phones, UUIDs, long hex / numeric IDs, and Facebook
    message-thread folder keys (when under a ``messages`` ancestor).
    """
    s = segment.strip()
    if not s:
        return segment

    if _under_messages(parent_parts):
        fb = redact_fb_thread_key(s)
        if fb is not None:
            return fb

    if patterns.EMAIL.match(s):
        return "{email}"
    if patterns.UUID.match(s):
        return "{uuid}"
    if patterns.PHONE_ISH.match(s) and sum(c.isdigit() for c in s) >= 7:
        return "{phone}"
    if patterns.LONG_HEX.match(s):
        return "{hex_id}"
    if patterns.NUMERIC_ID.match(s):
        return "{numeric_id}"
    return segment


def redact_path_parts(parts: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Redact each path part with awareness of ancestors (e.g. messages/)."""
    out: list[str] = []
    for part in parts:
        out.append(redact_path_segment(part, tuple(out)))
    return tuple(out)
