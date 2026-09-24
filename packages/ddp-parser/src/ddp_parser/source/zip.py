"""Zip containers: turn a ``ZipFile`` into ``Entry`` objects without extracting anything.

Spec: section 5. Owns everything zip-specific: filename decoding, unsafe paths, OS junk,
duplicate entries and the entry-count limit. Members are read lazily through ``Entry.open``.
"""

import unicodedata
from contextlib import suppress
from datetime import datetime
from functools import partial
from zipfile import ZipFile, ZipInfo

from ddp_parser.model import ParseWarning
from ddp_parser.options import Options
from ddp_parser.source.entry import Entry

_UTF8_FLAG = 0x800
_JUNK_FILES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})


def read_zip(
    archive: ZipFile, options: Options, warnings: list[ParseWarning], *, path: str = ""
) -> list[Entry]:
    """Entries of ``archive`` in archive order. ``path`` is the container's own node path,
    used for warnings about a nested zip.
    """
    entries: dict[tuple[str, ...], Entry] = {}
    ignored = 0
    for position, info in enumerate(archive.infolist()):
        if position == options.max_entries:
            skipped = len(archive.infolist()) - position
            warnings.append(_warning("too_many_entries", f"{skipped} entries skipped", path))
            break
        name = decode_name(info)
        parts = tuple(part for part in name.replace("\\", "/").split("/") if part)
        if not parts:
            continue
        if name.startswith(("/", "\\")) or ".." in parts or ":" in parts[0]:
            warnings.append(_warning("unsafe_path", f"rejected entry {name!r}", path))
            continue
        junk = is_junk(parts)
        if junk and not options.keep_ignored:
            ignored += 1
            continue
        if parts in entries:
            warnings.append(_warning("duplicate_entry", f"kept the last {name!r}", path))
        entries[parts] = Entry(
            parts=parts,
            size=info.file_size,
            modified=_modified(info),
            is_dir=info.is_dir(),
            ignored=junk,
            open=partial(archive.open, info),
        )
    if ignored:
        warnings.append(_warning("ignored_entries", f"{ignored} OS junk entries dropped", path))
    return list(entries.values())


def decode_name(info: ZipInfo) -> str:
    """The entry name as text (spec 5): UTF-8 if flagged, else CP437 unless it is valid UTF-8.

    ``zipfile`` already decodes unflagged names as CP437; many tools write UTF-8 without the
    flag, which turns "Kanäle" into "Kan├ñle". Re-encoding as CP437 and decoding as UTF-8 undoes
    that whenever it succeeds. Names are NFC-normalised (macOS writes decomposed characters).
    """
    name = info.filename
    if not info.flag_bits & _UTF8_FLAG:
        with suppress(UnicodeEncodeError, UnicodeDecodeError):
            name = name.encode("cp437").decode("utf-8")
    return unicodedata.normalize("NFC", name)


def is_junk(parts: tuple[str, ...]) -> bool:
    """OS artefacts from zipping or unzipping on the user's machine, not platform content."""
    return "__MACOSX" in parts or parts[-1].startswith("._") or parts[-1].lower() in _JUNK_FILES


def _modified(info: ZipInfo) -> datetime | None:
    """Zip timestamps are naive local time; the DOS minimum (1980-00-00) means "unset"."""
    try:
        return datetime(*info.date_time)  # noqa: DTZ001 - zip stores no timezone (spec 4.1)
    except ValueError:
        return None


def _warning(code: str, message: str, path: str) -> ParseWarning:
    return ParseWarning(code=code, message=message, path=path or None)
