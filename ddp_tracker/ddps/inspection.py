"""Inspecting an upload that isn't registered (held by ``checks.py``): its structure, and how its
data points compare with the counted uploads of its platform and format. Built from the schema
documents alone, so nothing of a held upload reaches the collected schema.

Each data point of the upload is:

- **known**: the counted uploads have it at the same path;
- **matched**: a ``moved``/``renamed`` suggestion links it to a known path (a moved or translated
  key);
- **new**: neither.

**Missing** are the known data points the upload has neither at their path nor matched. The share
of known and matched data points is the upload's similarity (``checks.similarity``).
"""

from collections import Counter
from dataclasses import dataclass, field

from ddp_parser import Candidate, children, from_dict, is_data_point, merge_trees, suggest, walk
from ddp_parser.model import Node
from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.services import type_label

KNOWN, MATCHED, NEW = "known", "matched", "new"
ITEM = "[]"


@dataclass
class Line:
    """A node of the upload's structure, with the nodes below it."""

    path: str
    name: str
    kind: str  # container, folder, file, media, unmatched, data
    label: str = ""  # type, shape and format: "string · datetime"
    status: str = ""  # of a data point: KNOWN, MATCHED or NEW; empty for the rest
    match: Candidate | None = None  # of a MATCHED one: the known path it corresponds to
    note: str = ""  # why a file wasn't read, how many files a group holds …
    children: list["Line"] = field(default_factory=list)
    has_new: bool = False  # something new here or below: shown opened

    @property
    def is_data_point(self) -> bool:
        return bool(self.status)


@dataclass(frozen=True)
class Inspection:
    root: Line
    counts: Counter[str]  # data points per status
    missing: list[str]  # known data points the upload lacks
    has_peers: bool  # anything to compare with (not the first upload of its kind)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def share(self) -> float | None:
        """Known and matched data points of all: None without peers or data points."""
        if not self.has_peers or not self.total:
            return None
        return (self.counts[KNOWN] + self.counts[MATCHED]) / self.total


def inspect(upload: Upload, peers: list[Upload]) -> Inspection:
    """``upload`` (with a document) against ``peers``, the counted uploads it is compared with."""
    assert upload.document is not None
    root = from_dict(upload.document).root
    roots = [from_dict(peer.document).root for peer in peers if peer.document is not None]
    statuses: dict[str, tuple[str, Candidate | None]] = {}
    missing: list[str] = []
    points = [node.path for node in walk(root) if is_data_point(node)]
    if roots:
        known = merge_trees(roots)
        known_paths = {node.path for node in walk(known)}
        suggested = suggest(known, root)
        for path in points:
            if path in known_paths:
                statuses[path] = (KNOWN, None)
            elif path in suggested:
                statuses[path] = (MATCHED, suggested[path][0])
            else:
                statuses[path] = (NEW, None)
        present = set(points) | {
            candidate.path for status, candidate in statuses.values() if candidate is not None
        }
        missing = [
            node.path for node in walk(known) if is_data_point(node) and node.path not in present
        ]
    else:
        statuses = dict.fromkeys(points, (NEW, None))
    counts = Counter(status for status, _ in statuses.values())
    return Inspection(_line(root, statuses), counts, missing, has_peers=bool(roots))


def _line(node: Node, statuses: dict[str, tuple[str, Candidate | None]]) -> Line:
    status, match = statuses.get(node.path, ("", None))
    line = Line(
        path=node.path,
        name=_name(node),
        kind=str(node.kind),
        label=" · ".join(
            part for part in (type_label(node), getattr(node, "shape", None), _format(node)) if part
        ),
        status=status,
        match=match,
        note=_note(node),
        children=[_line(child, statuses) for child in children(node)],
    )
    line.has_new = status == NEW or any(child.has_new for child in line.children)
    return line


def _name(node: Node) -> str:
    if not node.path:
        return "Upload"
    segment = node.path.rsplit("/", 1)[-1]
    return "each item" if segment == ITEM else (node.name or segment)


def _format(node: Node) -> str:
    return str(getattr(node, "format", None) or "")


def _note(node: Node) -> str:
    """What a filesystem node says beyond its name: why it wasn't read, a group's size."""
    reason = getattr(node, "reason", None)
    if reason is not None:
        error = getattr(node, "error", None)
        return f"not read: {reason}" + (f" ({error})" if error else "")
    files = getattr(node, "files", None) or getattr(node, "folders", None)
    return f"{files} merged" if files else ""
