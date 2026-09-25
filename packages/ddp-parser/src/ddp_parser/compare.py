"""Compare two schema trees: what was added, removed, moved or changed (spec 9.2).

Only structure is compared (kind, type, shape, format), never counts, sizes or timestamps, which
differ between any two exports. Two data-dependent details are ignored as well: whether a value
was ever ``null``, and ``mixed`` / ``empty`` shapes.
"""

from dataclasses import dataclass
from enum import StrEnum

from ddp_parser.model import DataNode, FileNode, JsonType, Node, Shape, walk

_UNSTABLE_SHAPES = frozenset({Shape.MIXED, Shape.EMPTY})
_MOVE_SIMILARITY = 0.5  # share of a moved subtree's relative paths both sides must have in common


class Status(StrEnum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MOVED_FROM = "moved_from"
    MOVED_TO = "moved_to"
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class Summary:
    """What is compared about one node."""

    kind: str
    name: str | None
    types: frozenset[str]  # without "null"
    shape: str | None
    format: str | None

    @classmethod
    def of(cls, node: Node) -> "Summary":
        types: frozenset[str] = frozenset()
        shape = fmt = None
        if isinstance(node, FileNode | DataNode):
            raw = node.type if isinstance(node.type, tuple) else (node.type,)
            types = frozenset(t for t in raw if t != JsonType.NULL)
            shape, fmt = node.shape, node.format
        return cls(node.kind, node.name, types, shape, fmt)

    def differences(self, other: "Summary") -> tuple[str, ...]:
        """Names of the fields that differ in a way that reflects the platform, not the data."""
        fields = []
        if self.kind != other.kind:
            fields.append("kind")
        if self.types and other.types and self.types != other.types:
            fields.append("type")
        stable = self.shape not in _UNSTABLE_SHAPES and other.shape not in _UNSTABLE_SHAPES
        if self.shape and other.shape and stable and self.shape != other.shape:
            fields.append("shape")
        if self.format and other.format and self.format != other.format:
            fields.append("format")
        return tuple(fields)


@dataclass(frozen=True, slots=True)
class Move:
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    fields: tuple[str, ...]
    before: Summary
    after: Summary


@dataclass(frozen=True, slots=True)
class Comparison:
    """``added`` / ``removed`` hold the top of each added / removed subtree only."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    moved: tuple[Move, ...]
    changed: tuple[Change, ...]

    def status(self, path: str) -> Status:
        """The status of any path of either tree (descendants inherit their subtree's)."""
        for move in self.moved:
            if within(path, move.old):
                return Status.MOVED_FROM
            if within(path, move.new):
                return Status.MOVED_TO
        if any(within(path, root) for root in self.added):
            return Status.ADDED
        if any(within(path, root) for root in self.removed):
            return Status.REMOVED
        if any(change.path == path for change in self.changed):
            return Status.CHANGED
        return Status.UNCHANGED

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.moved or self.changed)


def compare(base: Node, new: Node) -> Comparison:
    """How ``new`` differs from ``base`` (e.g. an upload from the accepted version)."""
    before = {node.path: Summary.of(node) for node in walk(base)}
    after = {node.path: Summary.of(node) for node in walk(new)}
    moves = find_moves(before.keys() - after.keys(), after.keys() - before.keys(), before, after)
    removed = _subtree_roots(
        {p for p in before.keys() - after.keys() if not any(within(p, m.old) for m in moves)}
    )
    added = _subtree_roots(
        {p for p in after.keys() - before.keys() if not any(within(p, m.new) for m in moves)}
    )
    changes = [
        Change(path, fields, before[path], after[path])
        for path in sorted(before.keys() & after.keys())
        if (fields := before[path].differences(after[path]))
    ]
    return Comparison(
        added=tuple(added),
        removed=tuple(removed),
        moved=tuple(moves),
        changed=tuple(changes),
    )


def within(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def _subtree_roots(paths: set[str]) -> list[str]:
    """The paths whose parent is not itself in ``paths``, sorted."""
    roots: list[str] = []
    for path in sorted(paths):
        if not roots or not within(path, roots[-1]):
            roots.append(path)
    return roots


def _relative(root: str, summaries: dict[str, Summary]) -> set[tuple[str, str]]:
    """The subtree below ``root`` as (relative path, kind) pairs, for similarity."""
    return {
        (path[len(root) :], summary.kind)
        for path, summary in summaries.items()
        if within(path, root)
    }


def find_moves(
    removed: set[str], added: set[str], before: dict[str, Summary], after: dict[str, Summary]
) -> list[Move]:
    """Pair removed and added nodes with the same name and kind and (mostly) the same subtree.

    Every removed / added path is a candidate, not just subtree tops: a folder moved into a new
    folder sits *inside* an added subtree. Shallow paths are paired first and their descendants
    are then skipped. Only unambiguous pairs count; anything else stays added / removed.
    """
    moves: list[Move] = []
    for old in sorted(removed, key=lambda path: (path.count("/"), path)):
        if any(within(old, move.old) for move in moves):
            continue
        key = (before[old].name, before[old].kind)
        olds = [p for p in _free(removed, moves, "old") if (before[p].name, before[p].kind) == key]
        news = [p for p in _free(added, moves, "new") if (after[p].name, after[p].kind) == key]
        if len(olds) != 1 or len(news) != 1:
            continue
        new = news[0]
        old_tree, new_tree = _relative(old, before), _relative(new, after)
        similarity = len(old_tree & new_tree) / len(old_tree | new_tree)
        if similarity >= _MOVE_SIMILARITY and not before[old].differences(after[new]):
            moves.append(Move(old, new))
    return sorted(moves, key=lambda move: move.old)


def _free(paths: set[str], moves: list[Move], side: str) -> list[str]:
    """``paths`` not inside an already paired subtree on that side."""
    taken = [getattr(move, side) for move in moves]
    return [path for path in paths if not any(within(path, root) for root in taken)]
