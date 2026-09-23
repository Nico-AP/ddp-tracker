"""Parse plain-text DDP files into nested data / list nodes.

TikTok (and similar) exports use free-form ``.txt`` with several recurring
shapes:

* ``Key: value`` lines (optionally under section headers without a colon)
* Parenthetical notes, e.g. ``(Note: ...)``
* Blank-line-separated records that share the same keys (e.g. Date/Username)
* Empty stubs: ``You have no data in this section`` / ``Du hast keine Daten…``,
  or files named ``no-data.txt``

The parser is heuristic, not policy-driven. Unrecognised layouts fall back to
a list of non-empty lines as data leaves so content is never dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..tree.nodes import data_leaf, list_node
from ...policy.empty import EMPTY_FILENAMES, is_empty_section_message

_NOTE_LINE = re.compile(r"^\((.+)\)$")
_KV_LINE = re.compile(r"^([^:]+):\s*(.*)$")


def _empty_tree(message: str = "") -> dict:
    """Represent an empty section as a data leaf (stub text kept for ``--full``).

    Schema modes classify known empty-section phrases as ``shape: "empty"``.
    """
    return data_leaf(message.strip())


def _is_empty_message(text: str) -> bool:
    return is_empty_section_message(text)


def _parse_kv_block(lines: list[str]) -> dict[str, dict] | None:
    """Parse a block of ``Key: value`` lines into data leaves; None if mixed."""
    out: dict[str, dict] = {}
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = _KV_LINE.match(line)
        if not m:
            return None
        key = m.group(1).strip()
        value = m.group(2).strip()
        if not key:
            return None
        out[key] = data_leaf(value)
    return out if out else None


def _split_blank_blocks(lines: list[str]) -> list[list[str]]:
    """Split into non-empty blocks separated by blank lines."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        if not raw.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(raw)
    if current:
        blocks.append(current)
    return blocks


def _try_repeated_records(lines: list[str]) -> dict | None:
    """If the file is blank-separated KV records with a shared key set, return a list."""
    blocks = _split_blank_blocks(lines)
    if len(blocks) < 2:
        return None

    parsed: list[dict[str, dict]] = []
    for block in blocks:
        # Allow a leading note only in the first block; otherwise require pure KV.
        body = block
        if len(parsed) == 0 and block and _NOTE_LINE.match(block[0].strip()):
            body = block[1:]
        obj = _parse_kv_block(body)
        if obj is None or not obj:
            return None
        parsed.append(obj)

    key_sets = [frozenset(p.keys()) for p in parsed]
    if len(set(key_sets)) != 1:
        return None
    # Single-field blocks are usually sectioned settings with blank lines, not records.
    if len(key_sets[0]) < 2:
        return None

    items = {str(i): parsed[i] for i in range(len(parsed))}
    return list_node(items)


def _start_section(root: dict, name: str) -> tuple[dict, str]:
    """Open a nested section under ``root[name]``; return (section_dict, name)."""
    nested: dict = {}
    root[name] = nested
    return nested, name


def _parse_sectioned(lines: list[str]) -> dict:
    """Parse notes + section headers + ``Key: value`` lines into a nested object.

    Section headers are either a bare line (no colon) or ``Name:`` with an empty
    value. An empty-section phrase under the active section replaces that
    section with an empty stub (message preserved) instead of becoming a key.
    """
    root: dict = {}
    current: dict = root
    section_key: str | None = None
    notes: list[dict] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        note = _NOTE_LINE.match(line)
        if note:
            notes.append(data_leaf(note.group(1).strip()))
            continue

        if _is_empty_message(line):
            if section_key is not None:
                # Keep section name; mark empty while preserving the stub text.
                root[section_key] = _empty_tree(line)
                current = root
                section_key = None
            else:
                root["_empty"] = _empty_tree(line)
            continue

        kv = _KV_LINE.match(line)
        if kv:
            key = kv.group(1).strip()
            value = kv.group(2).strip()
            if not key:
                continue
            if value == "":
                # ``Send Gifts History:`` → section header, not an empty data leaf.
                current, section_key = _start_section(root, key)
                continue
            current[key] = data_leaf(value)
            continue

        # Bare section header (e.g. ``Push Notification``).
        current, section_key = _start_section(root, line)

    if notes:
        root["_notes"] = list_node({str(i): n for i, n in enumerate(notes)})
    return root


def _fallback_lines(lines: list[str]) -> dict:
    """Keep every non-empty line as a list of data leaves."""
    items = {
        str(i): data_leaf(line.strip()) for i, line in enumerate(lines) if line.strip()
    }
    return list_node(items) if items else {}


def text_to_tree(text: str) -> dict:
    """Convert plain text into a nested content-tree fragment."""
    # Normalise newlines; keep original line bodies for parsing.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nonempty = [ln for ln in lines if ln.strip()]

    if not nonempty:
        return _empty_tree("")

    if len(nonempty) == 1 and _is_empty_message(nonempty[0]):
        return _empty_tree(nonempty[0].strip())

    repeated = _try_repeated_records(lines)
    if repeated is not None:
        # Preserve a leading file-level note if present.
        first = nonempty[0].strip()
        note = _NOTE_LINE.match(first)
        if note:
            return {
                "_notes": list_node({"0": data_leaf(note.group(1).strip())}),
                "records": repeated,
            }
        return repeated

    sectioned = _parse_sectioned(lines)
    # If we got nothing useful (e.g. free prose without colons), keep lines.
    if not sectioned:
        return _fallback_lines(lines)

    useful_keys = [k for k in sectioned if k != "_notes"]

    # Empty-section phrase mistaken for a header → {"Du hast keine…": {}}
    if (
        len(useful_keys) == 1
        and _is_empty_message(useful_keys[0])
        and sectioned.get(useful_keys[0]) == {}
    ):
        return _empty_tree(useful_keys[0])

    if not useful_keys and "_notes" not in sectioned:
        return _fallback_lines(lines)
    if not useful_keys and all(
        not _KV_LINE.match(ln.strip()) and not _NOTE_LINE.match(ln.strip())
        for ln in nonempty
    ):
        return _fallback_lines(lines)
    return sectioned


def parse_txt_tree(file_path: Path) -> dict:
    """Load one ``.txt`` file and return its nested data/list tree.

    Files named ``no-data.txt`` (any common spelling) are always treated as an
    empty section, using the file body as the message when present.
    """
    text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    if file_path.name.lower() in EMPTY_FILENAMES:
        message = text.strip() or "You have no data in this section"
        return _empty_tree(message)
    return text_to_tree(text)
