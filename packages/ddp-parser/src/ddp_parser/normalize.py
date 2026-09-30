"""Variable object keys (spec 3.6): keys that hold data rather than name a field.

Some exports key objects by data: a live stream's ID (``WatchLiveMap/7637478253594217238``), a
chat partner's username (``ChatHistory/Chat History with johndoe``). Kept as they are, these keys
put personal data into paths, and no two exports share the paths below them. Like look-alike
folders (spec 3.5), such keys are renamed to a segment with ``{*}`` and their nodes merged.

This runs on a built tree, so the same code normalizes a fresh parse and a stored document (with
rules added later). Per object, the first of these that applies to a key decides:

1. rules: ``Options.keep_keys`` keeps a key, ``Options.variable_keys`` renames it;
2. the key's shape: digits only, a UUID, email address, URL, date, time, unix timestamp, or a
   long hash-like token → ``{*}``;
3. shared words: two or more keys that differ only in their first or last word, and hold lists
   or objects that look alike → ``Chat History with {*}``;
4. look-alike values: three or more keys (all that are left) holding lists or objects that look
   alike → ``{*}``.
"""

import re
from collections import Counter
from dataclasses import dataclass
from functools import reduce

import msgspec

from ddp_parser.merge import merge_data
from ddp_parser.model import (
    ContainerNode,
    DataNode,
    FileNode,
    FilesystemNode,
    FolderNode,
    Shape,
    walk,
)
from ddp_parser.model.paths import ITEMS, ROOT, join, matches, split, unescape
from ddp_parser.options import Options
from ddp_parser.schematize.shapes import classify_string
from ddp_parser.similarity import look_alike
from ddp_parser.source.grouping import mask_name

VARIABLE = "{*}"

_KEY_SHAPES = frozenset(
    {Shape.UUID, Shape.EMAIL, Shape.URL, Shape.DATETIME, Shape.DATE, Shape.TIME}
)
_DIGITS = re.compile(r"^\d+$")
_HASH = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_-]{16,}$")
_SIMILARITY = 0.8  # stricter than folders (0.5): settings sections can look similar too
_MIN_LOOK_ALIKE = 3

type Valued = FileNode | DataNode


@dataclass(frozen=True, slots=True)
class Normalized:
    root: FilesystemNode
    renames: dict[str, str]  # old path → new path, for every node whose path changed


def normalize(root: FilesystemNode, options: Options) -> Normalized:
    """``root`` with variable object keys renamed and merged, and the paths that changed."""
    run = _Normalizer(options)
    normalized = run.filesystem(root)
    renames = {}
    for node in walk(root):
        new = run.translate(node.path)
        if new != node.path:
            renames[node.path] = new
    return Normalized(normalized, renames)


def is_variable_key(key: str) -> bool:
    """A key that is data by its shape alone (heuristic 2)."""
    if _DIGITS.match(key) or _HASH.match(key):
        return True
    shape, _ = classify_string(key, id_key=False)
    return shape in _KEY_SHAPES


class _Normalizer:
    def __init__(self, options: Options) -> None:
        self.options = options
        # new path of an object → {key: segment} for its renamed keys
        self.decisions: dict[str, dict[str, str]] = {}

    def translate(self, path: str) -> str:
        """The new path of ``path`` of the tree before normalizing."""
        new = ROOT
        for segment in split(path):
            new = join(new, self.decisions.get(new, {}).get(segment, segment))
        return new

    # --- tree --------------------------------------------------------------------------------

    def filesystem(self, node: FilesystemNode) -> FilesystemNode:
        match node:
            case ContainerNode() | FolderNode():
                children = tuple(self.filesystem(child) for child in node.children)
                return msgspec.structs.replace(node, children=children)
            case FileNode():
                return self.value(node, node.path)
            case _:
                return node

    def value[V: Valued](self, node: V, path: str) -> V:
        """``node`` moved to ``path``, its keys (and theirs, and so on) normalized."""
        properties = None
        if node.properties is not None:
            properties = {
                segment: self.value(child, join(path, segment))
                for segment, child in self.properties(path, node.properties).items()
            }
        items = self.value(node.items, join(path, ITEMS)) if node.items is not None else None
        return msgspec.structs.replace(node, path=path, properties=properties, items=items)

    def properties(self, path: str, properties: dict[str, DataNode]) -> dict[str, DataNode]:
        """The properties of the object at ``path`` by their new segment, merged where several
        keys got the same one.
        """
        segments = self.segments(path, properties)
        renamed = {key: segment for key, segment in segments.items() if key != segment}
        if not renamed:
            return properties
        self.decisions[path] = renamed
        groups: dict[str, list[tuple[str, DataNode]]] = {}
        for key, child in properties.items():
            groups.setdefault(segments.get(key, key), []).append((key, child))
        return {segment: self.merged(segment, members) for segment, members in groups.items()}

    def merged(self, segment: str, members: list[tuple[str, DataNode]]) -> DataNode:
        if len(members) == 1 and members[0][0] == segment:
            return members[0][1]
        threshold = self.options.shape_threshold
        node = reduce(lambda a, b: merge_data(a, b, threshold), [child for _, child in members])
        masks: Counter[str] = Counter()
        for key, child in members:
            mask = (child.name or "") if key == segment else _masked(segment, key)
            masks[mask] += child.keys or 1
        name = min(masks, key=lambda mask: (-masks[mask], mask))  # most common, ties by name
        keys = sum(child.keys or 1 for _, child in members)
        return msgspec.structs.replace(node, name=name, keys=keys)

    # --- decisions ---------------------------------------------------------------------------

    def segments(self, path: str, properties: dict[str, DataNode]) -> dict[str, str]:
        """The new segment of each key of the object at ``path`` that may change."""
        decided: dict[str, str] = {}
        undecided: list[str] = []
        for key in properties:
            full = join(path, key)
            if matches(full, self.options.keep_keys):
                continue
            rule = self.rule(full)
            if rule is not None:
                decided[key] = rule
            elif VARIABLE in key:
                continue  # normalized before
            elif is_variable_key(key):
                decided[key] = VARIABLE
            else:
                undecided.append(key)
        decided |= _shared_words(undecided, properties)
        rest = [key for key in undecided if key not in decided]
        if len(rest) >= _MIN_LOOK_ALIKE and _look_alike([properties[key] for key in rest]):
            decided |= dict.fromkeys(rest, VARIABLE)
        return decided

    def rule(self, full: str) -> str | None:
        """The segment a ``variable_keys`` rule gives the key at ``full``."""
        for pattern in self.options.variable_keys:
            if matches(full, (pattern,)):
                return unescape(pattern.rsplit("/", 1)[-1]).replace("*", VARIABLE)
        return None


def _shared_words(keys: list[str], properties: dict[str, DataNode]) -> dict[str, str]:
    """Keys that differ only in their first or last word, grouped under that pattern, if their
    values look alike (heuristic 3). Larger groups are tried first.
    """
    candidates: dict[str, list[str]] = {}
    for key in keys:
        head, space, last = key.rpartition(" ")
        if not space or not head.strip() or not last:
            continue
        _, _, tail = key.partition(" ")
        candidates.setdefault(f"{head} {VARIABLE}", []).append(key)
        candidates.setdefault(f"{VARIABLE} {tail}", []).append(key)
    decided: dict[str, str] = {}
    for pattern, members in sorted(candidates.items(), key=lambda item: (-len(item[1]), item[0])):
        free = [key for key in members if key not in decided]
        if len(free) >= 2 and _look_alike([properties[key] for key in free]):  # noqa: PLR2004 - two share a pattern
            decided |= dict.fromkeys(free, pattern)
    return decided


def _look_alike(nodes: list[DataNode]) -> bool:
    """Lists or objects whose insides look alike; single values never do."""
    return look_alike([_signature(node) for node in nodes], _SIMILARITY)


def _signature(node: DataNode) -> set[str]:
    """Every path below ``node``, relative to it."""
    return {below.path[len(node.path) :] for below in walk(node) if below is not node}


def _masked(segment: str, key: str) -> str:
    """The name of a renamed key: its variable part masked (``Chat History with xsx0``)."""
    before, variable, after = segment.partition(VARIABLE)
    if (
        variable
        and VARIABLE not in after
        and key.startswith(before)
        and key.endswith(after)
        and len(key) > len(before) + len(after)
    ):
        return before + mask_name(key[len(before) : len(key) - len(after)]) + after
    return mask_name(key)
