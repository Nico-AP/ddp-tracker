"""Group sibling files whose names only differ in their numbers (spec 3.4), and mask the names
of collapsed folders (spec 3.5).

``message_1.json`` … ``message_40.json`` share the pattern ``message_{n}.json`` (every run of
digits becomes ``{n}``) and become one node. A pattern needs at least two files; zips are never
grouped, since each is its own container.
"""

import re
from collections import defaultdict
from collections.abc import Iterable

PLACEHOLDER = "{n}"
_DIGITS = re.compile(r"\d+")


def group_names(names: Iterable[str]) -> dict[str, str]:
    """Map each groupable file name to its pattern; names not in any group are left out."""
    by_pattern: defaultdict[str, list[str]] = defaultdict(list)
    for name in names:
        if _DIGITS.search(name) and not name.lower().endswith(".zip"):
            by_pattern[pattern_of(name)].append(name)
    return {
        name: pattern
        for pattern, members in by_pattern.items()
        if len(members) >= 2  # noqa: PLR2004 - spec: a group needs two files
        for name in members
    }


_RUNS = re.compile(r"(.)\1+")


def pattern_of(name: str) -> str:
    """The name with every run of digits replaced by ``{n}``."""
    return _DIGITS.sub(PLACEHOLDER, name)


def mask_name(name: str) -> str:
    """Letters → ``x``, digits → ``0``, anything else → ``s``, runs collapsed: every thread
    folder ``johndoe_1234`` or ``annasmith_98765`` masks to ``xs0``.
    """
    masked = "".join("x" if c.isalpha() else "0" if c.isdigit() else "s" for c in name)
    return _RUNS.sub(r"\1", masked)
