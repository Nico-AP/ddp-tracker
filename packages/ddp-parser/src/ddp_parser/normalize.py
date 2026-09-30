"""Variable object keys (spec 3.6): keys that hold data rather than name a field.

Some exports key objects by data: a live stream's ID (``WatchLiveMap/7637478253594217238``), a
chat partner's username (``ChatHistory/Chat History with johndoe``). Kept as they are, these keys
put personal data into paths, and no two exports share the paths below them. Like look-alike
folders (spec 3.5), such keys are renamed to a segment with ``{*}`` and their nodes merged.

This runs on a built tree, so the same code normalizes a fresh parse and, through
``renormalize``, a stored document (with rules added later). Per object, the first of these that applies to a key decides:

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

from ddp_parser.compare import within
from ddp_parser.merge import merge_data
from ddp_parser.model import (
    SPEC_VERSION,
    ContainerNode,
    DataNode,
    Document,
    FileNode,
    FilesystemNode,
    FolderNode,
    Node,
    ParseWarning,
    Shape,
    UnmatchedNode,
    UnmatchedReason,
    walk,
)
from ddp_parser.model.paths import ITEMS, ROOT, join, matches, split, unescape
from ddp_parser.options import Options
from ddp_parser.schematize.shapes import classify_string
from ddp_parser.similarity import look_alike
from ddp_parser.source.grouping import mask_name
from ddp_parser.source.unwrap import same_name

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


@dataclass(frozen=True, slots=True)
class Renormalized:
    document: Document
    renames: dict[str, str]  # old path → new path, for every node whose path changed


def renormalize(document: Document, options: Options) -> Renormalized:
    """``document`` (e.g. stored before a rule was added) with ``options``' rules applied: a
    wrapper folder named like its zip lifted into it (spec 5) and variable keys renamed (spec
    3.6). ``options`` only contributes its key rules; they are recorded in ``document.options``.
    """
    lifted = lift_wrappers(document.root)
    normalized = normalize(lifted.root, options)
    renames = {}
    for node in walk(document.root):
        step = lifted.renames.get(node.path, node.path)
        new = normalized.renames.get(step, step)
        if new != node.path:
            renames[node.path] = new
    warnings = list(document.warnings)
    for old, new in lifted.renames.items():
        if new == old.rsplit("/", 1)[0]:  # a wrapper: its contents keep their names
            warnings.append(wrapper_warning(new))
    recorded = {
        **document.options,
        "variable_keys": list(options.variable_keys),
        "keep_keys": list(options.keep_keys),
    }
    renormalized = msgspec.structs.replace(
        document,
        spec_version=SPEC_VERSION,
        options=recorded,
        warnings=rename_warnings(warnings, renames),
        root=normalized.root,
    )
    return Renormalized(renormalized, renames)


def rename_warnings(
    warnings: list[ParseWarning], renames: dict[str, str]
) -> tuple[ParseWarning, ...]:
    """``warnings`` with the paths of renamed nodes, once each: the old paths can hold personal
    data, and merged keys may have warned alike.
    """
    renamed = (
        msgspec.structs.replace(warning, path=renames.get(warning.path, warning.path))
        if warning.path is not None
        else warning
        for warning in warnings
    )
    return tuple(dict.fromkeys(renamed))


def lift_wrappers(root: FilesystemNode) -> Normalized:
    """``root`` with the contents of every wrapper folder named like its zip moved up into the
    zip, as the parser does since spec 1.1 (``source/unwrap.py``). The folder's own path maps to
    its zip's.
    """
    lifts: list[tuple[str, str]] = []  # (wrapper path, container path), outer ones first

    def visit(node: FilesystemNode) -> FilesystemNode:
        match node:
            case ContainerNode():
                children = node.children
                wrapper = _wrapper(node)
                if wrapper is not None:
                    lifts.append((wrapper.path, node.path))
                    moved = tuple(
                        _moved(child, wrapper.path, node.path) for child in wrapper.children
                    )
                    others = tuple(child for child in children if child is not wrapper)
                    children = tuple(sorted(moved + others, key=lambda child: child.name or ""))
                return msgspec.structs.replace(node, children=tuple(map(visit, children)))
            case FolderNode():
                return msgspec.structs.replace(node, children=tuple(map(visit, node.children)))
            case _:
                return node

    lifted = visit(root)
    renames = {}
    for node in walk(root):
        path = node.path
        for wrapper, container in lifts:
            if within(path, wrapper):
                path = container + path[len(wrapper) :]
        if path != node.path:
            renames[node.path] = path
    return Normalized(lifted, renames)


def _wrapper(container: ContainerNode) -> FolderNode | None:
    """The container's only folder (OS junk aside) if it is named like the container."""
    content = [child for child in container.children if not _is_junk(child)]
    if len(content) != 1 or container.name is None:
        return None
    folder = content[0]
    if isinstance(folder, FolderNode) and folder.children and folder.name is not None:
        return folder if same_name(folder.name, container.name) else None
    return None


def _is_junk(node: FilesystemNode) -> bool:
    """OS junk kept with ``Options.keep_ignored``: ignored files, or folders holding only them."""
    files = [below for below in walk(node) if not isinstance(below, FolderNode)]
    return bool(files) and all(
        isinstance(below, UnmatchedNode) and below.reason == UnmatchedReason.IGNORED
        for below in files
    )


def _moved[N: Node](node: N, old: str, new: str) -> N:
    """``node`` and its subtree with the path prefix ``old`` replaced by ``new``."""
    path = new + node.path[len(old) :]
    match node:
        case ContainerNode() | FolderNode():
            children = tuple(_moved(child, old, new) for child in node.children)
            return msgspec.structs.replace(node, path=path, children=children)
        case FileNode() | DataNode():
            properties = (
                {key: _moved(child, old, new) for key, child in node.properties.items()}
                if node.properties is not None
                else None
            )
            items = _moved(node.items, old, new) if node.items is not None else None
            return msgspec.structs.replace(node, path=path, properties=properties, items=items)
        case _:
            return msgspec.structs.replace(node, path=path)


def wrapper_warning(path: str) -> ParseWarning:
    return ParseWarning(
        code="wrapper_folder",
        message="removed the top-level folder named like the zip",
        path=path or None,
    )


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
