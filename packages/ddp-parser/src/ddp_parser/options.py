"""Parser options (spec: ``options``).

One frozen object holding every tunable. It is copied into ``Document.options`` so a stored
schema records how it was produced.
"""

import msgspec

from ddp_parser.model.document import OptionValue

_MIB = 1024 * 1024


class Options(msgspec.Struct, frozen=True, kw_only=True):
    samples: bool = False
    max_samples: int = 3
    # shapes whose sample strings are masked (samples.py); the default covers identifying ones
    masked_shapes: tuple[str, ...] = ("email", "url", "text", "alphanumeric", "uuid")
    shape_threshold: float = 0.95

    # Zip handling (spec 5). Size limits apply to what the parser reads (files it parses and
    # nested zips); media files are only ever read for their first few bytes.
    max_depth: int = 3  # nested zips below this depth become ``unmatched`` (``too_large``)
    max_entries: int = 200_000  # per container; further entries are skipped with a warning
    max_entry_size: int = 256 * _MIB
    max_total_size: int = 4096 * _MIB
    keep_ignored: bool = False  # list OS junk (``__MACOSX/``, ``.DS_Store`` …) as ``ignored``

    # Collapsing look-alike sibling folders (spec 3.5). Each rule is a folder path whose
    # subfolders are always (``collapse_folders``) or never (``keep_folders``) collapsed; ``*``
    # matches any one path segment, e.g. ``/messages/*``. Without a rule, a heuristic decides.
    collapse_folders: tuple[str, ...] = ()
    keep_folders: tuple[str, ...] = ()

    # Variable object keys (spec 3.6): keys that hold data (a username, an ID) rather than name a
    # field. Each rule is a key path whose last segment is a glob on the key; its ``*`` becomes
    # ``{*}`` in the path, e.g. ``/data.json/Chats/Chat with *`` → ``/data.json/Chats/Chat with
    # {*}``. ``keep_keys`` are key paths that are never renamed. Without a rule, heuristics decide.
    variable_keys: tuple[str, ...] = ()
    keep_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, OptionValue]:
        """Plain JSON data (tuples become lists), as recorded in ``Document.options``."""
        data: dict[str, OptionValue] = msgspec.json.decode(msgspec.json.encode(self))
        return data
