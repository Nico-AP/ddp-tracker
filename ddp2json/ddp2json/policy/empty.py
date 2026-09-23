"""Known empty-section stub phrases (TikTok TXT and similar).

Shared by the TXT parser and schema describe so empty stubs stay consistent.
"""

from __future__ import annotations

import re
from pathlib import Path

# Platform stub filenames that always mean an empty section.
EMPTY_FILENAMES = frozenset(
    {
        "no-data.txt",
        "nodata.txt",
        "no_data.txt",
    }
)

EMPTY_SECTION = re.compile(
    r"^(?:"
    r"you have no data in this section"
    r"|du hast keine daten in diesem abschnitt"
    r")\.?$",
    re.IGNORECASE,
)


def is_empty_section_message(text: str) -> bool:
    """True if ``text`` is a platform empty-section stub phrase."""
    return bool(EMPTY_SECTION.match(text.strip()))


def is_empty_stub_path(path: str) -> bool:
    """True if ``path`` is a platform empty-section stub filename."""
    return Path(path).name.lower() in EMPTY_FILENAMES
