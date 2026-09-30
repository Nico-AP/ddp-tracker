"""Merge the schema trees of several documents into one (spec 9.1).

Used to build a platform's accepted schema version from several uploads: nodes at the same path
are unified with the rules of spec 3.4 (stats summed, type unions, shape counts summed, formats
kept or counted, lengths and ranges widened, optional keys). ``presence`` records in how many of
the documents each path occurs, which tells "every export has this" from "some exports do".
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import msgspec

from ddp_parser.model import (
    ContainerNode,
    DataNode,
    Document,
    FileNode,
    FilesystemNode,
    FolderNode,
    JsonType,
    Kind,
    MediaNode,
    MinMax,
    Samples,
    Shape,
    Stats,
    UnmatchedNode,
    walk,
)
from ddp_parser.schematize import dominant_shape, type_union

# When the same path has different kinds in different exports, keep the most informative one:
# a file one export could parse beats the same file another export failed on.
_KIND_RANK = {Kind.FILE: 0, Kind.CONTAINER: 1, Kind.FOLDER: 2, Kind.MEDIA: 3, Kind.UNMATCHED: 4}

type Fields = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Merged:
    root: FilesystemNode
    presence: dict[str, int]  # path → number of documents it occurs in
    documents: int


def merge(documents: Sequence[Document], *, shape_threshold: float = 0.95) -> Merged:
    """Merge the trees of ``documents`` (at least one) into one tree."""
    if not documents:
        msg = "merge() needs at least one document"
        raise ValueError(msg)
    presence: Counter[str] = Counter()
    for document in documents:
        presence.update({node.path for node in walk(document.root)})
    root = merge_trees([document.root for document in documents], shape_threshold=shape_threshold)
    return Merged(root=root, presence=dict(presence), documents=len(documents))


def merge_trees(
    roots: Sequence[FilesystemNode], *, shape_threshold: float = 0.95
) -> FilesystemNode:
    """Merge bare trees (e.g. the roots of several uploads' schema documents)."""
    if not roots:
        msg = "merge_trees() needs at least one tree"
        raise ValueError(msg)
    root = roots[0]
    for other in roots[1:]:
        root = merge_filesystem(root, other, shape_threshold)
    return root


def merge_filesystem(a: FilesystemNode, b: FilesystemNode, threshold: float) -> FilesystemNode:
    if type(a) is not type(b):
        return a if _KIND_RANK[a.kind] <= _KIND_RANK[b.kind] else b
    meta = _merge_meta(a, b)
    match a, b:
        case ContainerNode(), ContainerNode():
            children = _merge_children(a.children, b.children, threshold)
            return msgspec.structs.replace(a, **meta, children=children)
        case FolderNode(), FolderNode():
            children = _merge_children(a.children, b.children, threshold)
            folders = _add_members(a.folders, b.folders)
            return msgspec.structs.replace(a, **meta, folders=folders, children=children)
        case FileNode(), FileNode():
            fields = merge_fields(a, b, threshold)
            return msgspec.structs.replace(
                a, **meta, files=_add_members(a.files, b.files), **fields
            )
        case MediaNode(), MediaNode():
            return msgspec.structs.replace(a, **meta, files=_add_members(a.files, b.files))
        case UnmatchedNode(), UnmatchedNode():
            return msgspec.structs.replace(a, **meta, files=_add_members(a.files, b.files))
    msg = f"cannot merge {type(a).__name__} and {type(b).__name__}"  # pragma: no cover
    raise TypeError(msg)  # pragma: no cover


def merge_data(a: DataNode, b: DataNode, threshold: float) -> DataNode:
    keys = _add_counts(a.keys, b.keys)
    return msgspec.structs.replace(a, keys=keys, **merge_fields(a, b, threshold))


def merge_fields(a: FileNode | DataNode, b: FileNode | DataNode, threshold: float) -> Fields:
    """The unified schema fields of two value positions (spec 3.4)."""
    shapes = Counter(a.shapes) + Counter(b.shapes)
    shape = dominant_shape(shapes, threshold)
    fmt, formats = _merge_formats(a, b, shape)
    return {
        "type": type_union(_types(a) | _types(b)),
        "shape": shape,
        "format": fmt,
        "formats": formats,
        "length": _widen(a.length, b.length),
        "range": _widen(a.range, b.range),
        "stats": Stats(
            count=a.stats.count + b.stats.count,
            present=a.stats.present + b.stats.present,
            null=a.stats.null + b.stats.null,
        ),
        "shapes": dict(shapes),
        "properties": _merge_properties(a, b, threshold),
        "items": _merge_items(a.items, b.items, threshold),
        "samples": _merge_samples(a.samples, b.samples),
    }


# --- helpers ---------------------------------------------------------------------------------


def _merge_meta(a: FilesystemNode, b: FilesystemNode) -> Fields:
    stamps = [stamp for stamp in (a.modified, b.modified) if stamp is not None]
    mime_from = a if a.mime else b
    return {
        "size_bytes": _add_counts(a.size_bytes, b.size_bytes),
        "modified": max(stamps) if stamps else None,
        "ext": a.ext or b.ext,
        "mime": mime_from.mime,
        "mime_source": mime_from.mime_source,
    }


def _merge_children(
    a: tuple[FilesystemNode, ...], b: tuple[FilesystemNode, ...], threshold: float
) -> tuple[FilesystemNode, ...]:
    merged = {child.path: child for child in a}
    for child in b:
        existing = merged.get(child.path)
        merged[child.path] = (
            child if existing is None else merge_filesystem(existing, child, threshold)
        )
    return tuple(sorted(merged.values(), key=lambda node: node.name or ""))


def _merge_properties(
    a: FileNode | DataNode, b: FileNode | DataNode, threshold: float
) -> dict[str, DataNode] | None:
    """Union of keys. A key missing on one side still counts that side's objects, so it shows
    up as optional (``present < count``).
    """
    if a.properties is None and b.properties is None:
        return None
    a_props, b_props = a.properties or {}, b.properties or {}
    a_objects, b_objects = _objects(a), _objects(b)
    merged: dict[str, DataNode] = {}
    for key in {**a_props, **b_props}:
        if key in a_props and key in b_props:
            merged[key] = merge_data(a_props[key], b_props[key], threshold)
        elif key in a_props:
            merged[key] = _add_missing(a_props[key], b_objects)
        else:
            merged[key] = _add_missing(b_props[key], a_objects)
    return merged


def _merge_items(a: DataNode | None, b: DataNode | None, threshold: float) -> DataNode | None:
    if a is None or b is None:
        return a or b
    return merge_data(a, b, threshold)


def _objects(node: FileNode | DataNode) -> int:
    """How many objects were seen at this position: the ``count`` of each of its properties."""
    first = next(iter((node.properties or {}).values()), None)
    return 0 if first is None else first.stats.count


def _add_missing(node: DataNode, objects: int) -> DataNode:
    if not objects:
        return node
    stats = msgspec.structs.replace(node.stats, count=node.stats.count + objects)
    return msgspec.structs.replace(node, stats=stats)


def _types(node: FileNode | DataNode) -> set[JsonType]:
    return {node.type} if isinstance(node.type, JsonType) else set(node.type)


def _format_counts(node: FileNode | DataNode, shape: Shape | None) -> Counter[str]:
    """How many values of ``shape`` had which format, as far as the node records it."""
    if shape is None or node.shape != shape:
        return Counter()
    if node.formats:
        return Counter(node.formats)
    if node.format:
        return Counter({node.format: node.shapes.get(shape, 1)})
    return Counter()


def _merge_formats(
    a: FileNode | DataNode, b: FileNode | DataNode, shape: Shape | None
) -> tuple[str | None, dict[str, int] | None]:
    counts = _format_counts(a, shape) + _format_counts(b, shape)
    if len(counts) == 1:
        return next(iter(counts)), None
    return None, (dict(sorted(counts.items())) or None)


def _widen(a: MinMax | None, b: MinMax | None) -> MinMax | None:
    if a is None or b is None:
        return a or b
    return MinMax(min(a.min, b.min), max(a.max, b.max))


def _merge_samples(a: Samples | None, b: Samples | None) -> Samples | None:
    if a is None or b is None:
        return a or b
    limit = max(len(a.values), len(b.values))
    values = tuple(dict.fromkeys((*a.values, *b.values)))[:limit]
    return Samples(values, redacted=a.redacted or b.redacted)


def _add_counts(a: int | None, b: int | None) -> int | None:
    """Sum of two optional amounts (sizes, merged keys); ``None`` only if both are unknown."""
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def _add_members(a: int | None, b: int | None) -> int | None:
    """Sum of ``files`` / ``folders`` counts, where ``None`` means a single, ungrouped one."""
    if a is None and b is None:
        return None
    return (a or 1) + (b or 1)
