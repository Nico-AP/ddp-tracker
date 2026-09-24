"""``Entry``: one file or folder inside a container, and ``ReadBudget`` for reading entries.

Every source produces entries; parsers only ever see an entry's bytes, never zip internals.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import IO

from ddp_parser.errors import LimitExceededError
from ddp_parser.options import Options


@dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    parts: tuple[str, ...]  # decoded name segments below the container, e.g. ("inbox", "a.json")
    size: int  # declared uncompressed size; 0 for folders
    modified: datetime | None  # as stored: naive, no offset
    is_dir: bool = False
    ignored: bool = False  # OS junk kept because of ``Options.keep_ignored``
    open: Callable[[], IO[bytes]]

    @property
    def name(self) -> str:
        return self.parts[-1]

    def header(self, size: int = 262) -> bytes:
        """The first bytes, for magic-number detection (cheap even for large media files)."""
        with self.open() as stream:
            return stream.read(size)


class ReadBudget:
    """Enforces the per-entry and total size limits (spec 5) on everything the parser reads."""

    def __init__(self, options: Options) -> None:
        self._max_entry = options.max_entry_size
        self._remaining = options.max_total_size

    def read(self, entry: Entry) -> bytes:
        if entry.size > self._max_entry:
            msg = f"{entry.size} bytes exceeds max_entry_size ({self._max_entry})"
            raise LimitExceededError(msg)
        if entry.size > self._remaining:
            msg = "reading it would exceed max_total_size"
            raise LimitExceededError(msg)
        with entry.open() as stream:
            data = stream.read(entry.size + 1)
        if len(data) > entry.size:  # zipfile never does this; a guard for other sources
            msg = "entry is larger than its declared size"
            raise LimitExceededError(msg)
        self._remaining -= len(data)
        return data
