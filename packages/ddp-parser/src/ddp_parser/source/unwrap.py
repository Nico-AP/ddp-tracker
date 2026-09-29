"""Drop a wrapper folder named like its zip (spec 5).

Unzipping an export and zipping it again puts everything below one folder named after the
original zip: ``instagram-johndoe-2026-09-29-AbCd1234/ads_information/…``. That name holds the
username and differs per export, so it would put personal data into every path and keep the
export from sharing paths with any other. The folder is dropped when it holds everything and its
name matches the zip's.
"""

import re
import unicodedata
from dataclasses import replace
from pathlib import PurePosixPath

from ddp_parser.source.entry import Entry

# what operating systems and browsers append to a copy: "export (1)", "export 2", "export - Copy"
_COPY_SUFFIX = re.compile(r"(\s*\(\d+\)|\s+\d+|\s*-?\s*copy(\s*\d+)?)$", re.IGNORECASE)


def same_name(folder: str, container: str) -> bool:
    """True if ``folder`` is named like the zip ``container`` (without its extension), ignoring
    case, Unicode normalisation and copy suffixes.
    """
    return _key(folder) == _key(PurePosixPath(container).stem)


def _key(name: str) -> str:
    name = unicodedata.normalize("NFC", name).casefold().strip()
    return _COPY_SUFFIX.sub("", name)


def unwrap(entries: list[Entry], container: str | None) -> tuple[list[Entry], bool]:
    """``entries`` without their shared top-level folder if it is named like ``container``, and
    whether it was dropped. OS junk (``__MACOSX/`` …) is not taken into account and stays as it is
    unless it lies inside the folder.
    """
    content = [entry for entry in entries if not entry.ignored]
    tops = {entry.parts[0] for entry in content}
    if container is None or len(tops) != 1:
        return entries, False
    top = tops.pop()
    has_files = any(not entry.is_dir and len(entry.parts) > 1 for entry in content)
    if not has_files or not same_name(top, container):
        return entries, False
    unwrapped = [
        replace(entry, parts=entry.parts[1:]) if entry.parts[0] == top else entry
        for entry in entries
        if entry.parts != (top,)
    ]
    return unwrapped, True
