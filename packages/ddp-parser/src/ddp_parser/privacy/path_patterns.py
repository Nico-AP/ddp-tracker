"""Path-segment patterns for identifying archive folder and key names.

Adapted from ``ddp2json.policy.scrub.path_patterns`` (ddp_tooling).
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
PHONE_ISH = re.compile(r"^\+?\d[\d\s().-]{6,}\d$")
LONG_HEX = re.compile(r"^[0-9a-f]{16,}$", re.I)
NUMERIC_ID = re.compile(r"^\d{6,}$")

# Facebook message-thread folders: "alice_123…" or "aliceand12others_123…".
FB_THREAD_KEY = re.compile(
    r"^(?P<label>.+?)(?:and(?P<others>\d+)others)?_(?P<uid>\d{6,})$",
    re.IGNORECASE,
)

# Ancestor folder name that enables FB thread-key redaction.
MESSAGES_ANCESTOR = "messages"
