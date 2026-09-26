"""Suggest which known schema positions a new upload's unknown data points correspond to
(spec 9.3).

Used to keep a data point's identity when its location changes: a file or key that moved, or a
key that is named differently (renamed, or translated in an export requested in another
language). Suggestions only; a curator confirms them.
"""

from dataclasses import dataclass

from ddp_parser.compare import Summary, find_moves, within
from ddp_parser.model import DataNode, FileNode, JsonType, Kind, Node, children, walk
from ddp_parser.model.paths import ITEMS

_STRUCTURAL_KINDS = frozenset({Kind.FOLDER, Kind.CONTAINER})
_STRUCTURE = frozenset({JsonType.OBJECT, JsonType.ARRAY})
_SIMILARITY = 0.5  # share of relative sub-paths a renamed list/object must have in common

type Mapping = tuple[str, float]  # (known path, how sure we are)


@dataclass(frozen=True, slots=True)
class Candidate:
    path: str  # the known path the new data point may correspond to
    reason: str  # "moved" or "renamed"
    score: float  # 0-1, higher is more likely


def is_data_point(node: Node) -> bool:
    """A node that carries meaning of its own (spec 9.3): a value or a list in parsed content, a
    list's item (``…/[]``: the value or entity it holds, e.g. "ID", "watched video"), a parsed
    file whose content is a list (a JSON array, a CSV's rows), or a media file.

    Objects only group keys unless they are a list's item, and other files, folders and
    containers only describe where data lies.
    """
    if node.kind == Kind.MEDIA:
        return True
    if node.path.endswith("/" + ITEMS):
        return isinstance(node, DataNode)
    if isinstance(node, FileNode):
        types = node.type if isinstance(node.type, tuple) else (node.type,)
        return JsonType.ARRAY in types
    return isinstance(node, DataNode) and not _is_plain_object(node)


def _is_plain_object(node: DataNode) -> bool:
    """An object (possibly nullable), as opposed to a value, a list or a mix of types."""
    types = set(node.type) if isinstance(node.type, tuple) else {node.type}
    return types - {JsonType.NULL} == {JsonType.OBJECT}


def _is_matchable(node: Node) -> bool:
    """Nodes the matcher follows: data points, and files (a renamed file carries its content
    along), but not folders, containers or the root.
    """
    return node.kind not in _STRUCTURAL_KINDS and node.path != ""


def is_structure(node: Node) -> bool:
    """A list or an object (possibly empty), as opposed to a single value or an opaque file."""
    if isinstance(node, FileNode | DataNode):
        types = node.type if isinstance(node.type, tuple) else (node.type,)
        return bool(_STRUCTURE.intersection(types))
    return False


def parent_of(path: str) -> str:
    return path.rsplit("/", 1)[0]


def _relative(root: str, nodes: dict[str, Node]) -> set[str]:
    return {path[len(root) :] for path in nodes if within(path, root)}


def suggest(known: Node, new: Node) -> dict[str, list[Candidate]]:
    """Candidates for every data point of ``new`` whose path is not in ``known``, best first.

    Nodes are visited parents first, so a list or object with one clear rename candidate lets
    its children be matched through it (``Kommentare/Datum`` → ``Comments/Date``).
    """
    return _Matcher(known, new).run()


class _Matcher:
    def __init__(self, known: Node, new: Node) -> None:
        self.before = {node.path: node for node in walk(known)}
        self.after = {node.path: node for node in walk(new)}
        self.moves = find_moves(
            self.before.keys() - self.after.keys(),
            self.after.keys() - self.before.keys(),
            {path: Summary.of(node) for path, node in self.before.items()},
            {path: Summary.of(node) for path, node in self.after.items()},
        )
        self.renamed: dict[str, Mapping] = {}  # new path of a renamed list/object → known path

    def run(self) -> dict[str, list[Candidate]]:
        suggestions: dict[str, list[Candidate]] = {}
        for path, node in self.after.items():
            if path in self.before or not _is_matchable(node):
                continue
            mapped = self.to_known(path)
            if mapped is not None and mapped[0] in self.before:
                suggestions[path] = [Candidate(mapped[0], "moved", mapped[1])]
                continue
            candidates = self.renames(path, node)
            if not candidates:
                continue
            suggestions[path] = candidates
            clear = len(candidates) == 1 or candidates[0].score > candidates[1].score
            if is_structure(node) and clear:
                self.renamed[path] = (candidates[0].path, candidates[0].score)
        # files are followed (above) but only data points are offered
        return {
            path: found for path, found in suggestions.items() if is_data_point(self.after[path])
        }

    def to_known(self, path: str) -> Mapping | None:
        """The known path corresponding to ``path`` of ``new``: itself, via a move, or via a
        suggested rename of an ancestor (then only as sure as that rename).
        """
        if path in self.before:
            return path, 1.0
        for move in self.moves:
            if within(path, move.new):
                return move.old + path[len(move.new) :], 1.0
        for prefix in sorted(self.renamed, key=len, reverse=True):
            if within(path, prefix):
                old, score = self.renamed[prefix]
                return old + path[len(prefix) :], score
        return None

    def to_new(self, path: str) -> str:
        """The path of ``new`` corresponding to known ``path`` (inverse of ``to_known``)."""
        for move in self.moves:
            if within(path, move.old):
                return move.new + path[len(move.old) :]
        for new_prefix, (old, _) in self.renamed.items():
            if within(path, old):
                return new_prefix + path[len(old) :]
        return path

    def renames(self, path: str, node: Node) -> list[Candidate]:
        """Known siblings that are absent from ``new`` and look the same: probably this key
        under another name (e.g. ``Date`` in an English export, ``Datum`` in a German one).
        Lists and objects must also look alike inside.
        """
        parent = self.to_known(parent_of(path))
        if parent is None or parent[0] not in self.before:
            return []
        new_siblings = children(self.after[parent_of(path)])
        position = next(i for i, sibling in enumerate(new_siblings) if sibling.path == path)
        summary = Summary.of(node)
        inside = _relative(path, self.after) if is_structure(node) else set()
        candidates = []
        for index, sibling in enumerate(children(self.before[parent[0]])):
            if not _is_matchable(sibling) or self.to_new(sibling.path) in self.after:
                continue
            other = Summary.of(sibling)
            if (
                other.kind != summary.kind
                or other.types != summary.types
                or summary.differences(other)
            ):
                continue
            score = 0.5 + (0.3 if index == position else 0.0)
            if inside:
                similarity = _similarity(inside, _relative(sibling.path, self.before))
                if similarity < _SIMILARITY:
                    continue
                score += 0.2 * similarity
            elif summary.format and summary.format == other.format:
                score += 0.2
            elif summary.shape and summary.shape == other.shape:
                score += 0.1
            candidates.append(Candidate(sibling.path, "renamed", round(score * parent[1], 2)))
        return sorted(candidates, key=lambda candidate: -candidate.score)


def _similarity(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b)
