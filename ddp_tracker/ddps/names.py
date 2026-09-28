"""Anonymized file names: an uploaded DDP's name can identify its uploader
(``tiktok_johndoe_2024-05-01.zip``), so only a masked form is stored.

Words in ``WHITELIST`` stay, any other letter becomes ``x``, every digit ``0``; everything else
(``_``, ``-``, spaces, brackets …) and the extension stay: ``tiktok_xxxxxxx_0000-00-00.zip``.
"""

import re
from pathlib import PurePosixPath, PureWindowsPath

# Words that identify no one: formats, generic export terms, platforms. Matched case-insensitively
# against whole runs of letters. Add words here (with a test), never names of people or accounts.
WHITELIST = frozenset(
    {
        # formats
        "zip",
        "json",
        "csv",
        # generic export terms
        "data",
        "export",
        "download",
        "archive",
        "takeout",
        "account",
        "user",
        "my",
        "your",
        "personal",
        "information",
        "info",
        "activity",
        "request",
        "backup",
        "part",
        "file",
        "files",
        "copy",
        "final",
        "new",
        # platforms
        "tiktok",
        "instagram",
        "facebook",
        "meta",
        "youtube",
        "google",
        "twitter",
        "linkedin",
        "snapchat",
        "whatsapp",
        "threads",
        "reddit",
        "spotify",
        "netflix",
        "amazon",
        "apple",
        "pinterest",
        "discord",
        "telegram",
        "bluesky",
    }
)

_RUNS = re.compile(r"[^\W\d_]+|\d+|[\W_]+")  # letters | digits | anything else


def anonymize_file_name(name: str) -> str:
    """``name`` with every non-whitelisted word masked (``x`` per letter) and every digit ``0``;
    separators and whitelisted words (the extensions among them) stay. Idempotent."""
    base = PureWindowsPath(PurePosixPath(name).name).name  # some browsers send a full path
    return "".join(_mask(run) for run in _RUNS.findall(base))


def _mask(run: str) -> str:
    if run.isdigit():
        return "0" * len(run)
    if run.isalpha():
        return run if run.lower() in WHITELIST else "x" * len(run)
    return run
