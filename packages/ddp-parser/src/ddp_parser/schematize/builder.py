"""``NodeBuilder``: observe values at one schema position, then ``build()`` the frozen node.

One builder describes one position. Unifying array items, merging grouped files and reading CSV
rows are all the same operation: observing more values into the same builder. Raw values are not
kept (except up to ``max_samples`` opt-in samples).

``build()`` makes every decision that needs all values seen: ``count`` derived from the parent,
the dominant shape against the threshold, the ``format``, type unions, samples.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

import msgspec

from ddp_parser.model import DataNode, JsonType, MinMax, ParseWarning, Shape, Stats
from ddp_parser.model.paths import ITEMS, join
from ddp_parser.options import Options
from ddp_parser.schematize.date_formats import resolve_format
from ddp_parser.schematize.samples import build_samples
from ddp_parser.schematize.shapes import classify_number, classify_string, is_id_key

type Scalar = str | int | float | bool


class NodeBuilder:
    def __init__(self, name: str | None, path: str, *, max_samples: int = 0) -> None:
        self.name = name
        self.path = path
        self._max_samples = max_samples
        self._id_key = is_id_key(name)

        self._present = 0  # values observed here, nulls included
        self._nulls = 0
        self._objects = 0  # how many of them were objects: the ``count`` of each property
        self._types: set[JsonType] = set()
        self._shapes: Counter[Shape] = Counter()
        self._fits: defaultdict[Shape, Counter[frozenset[str]]] = defaultdict(Counter)
        self._length: tuple[int, int] | None = None
        self._range: tuple[int | float, int | float] | None = None
        self._samples: dict[tuple[type, Scalar], tuple[Scalar, Shape | None]] = {}
        self._properties: dict[str, NodeBuilder] = {}
        self._items: NodeBuilder | None = None

    # --- observing ---------------------------------------------------------------------------

    def observe(self, value: object) -> None:
        """Record one value at this position."""
        if isinstance(value, list):
            self.observe_array(value)
            return
        self._present += 1
        match value:
            case None:
                self._nulls += 1
                self._types.add(JsonType.NULL)
            case dict():
                self._observe_object(value)
            case bool():
                self._types.add(JsonType.BOOLEAN)
                self._sample(value, None)
            case int() | float():
                self._observe_number(value)
            case str():
                self._observe_string(value)
            case _:
                msg = f"not a JSON value: {type(value).__name__}"
                raise TypeError(msg)

    def observe_array(self, items: Iterable[object]) -> None:
        """Record one array; ``items`` may be a lazy iterator (CSV rows, JSON Lines)."""
        self._present += 1
        self._types.add(JsonType.ARRAY)
        size = 0
        for item in items:
            if self._items is None:
                self._items = NodeBuilder(
                    None, join(self.path, ITEMS), max_samples=self._max_samples
                )
            self._items.observe(item)
            size += 1
        self._extend_length(size)

    def _observe_object(self, value: dict[str, object]) -> None:
        self._types.add(JsonType.OBJECT)
        self._objects += 1
        for key, child_value in value.items():
            child = self._properties.get(key)
            if child is None:
                child = NodeBuilder(key, join(self.path, key), max_samples=self._max_samples)
                self._properties[key] = child
            child.observe(child_value)

    def _observe_number(self, value: float) -> None:
        self._types.add(JsonType.INTEGER if isinstance(value, int) else JsonType.NUMBER)
        low, high = self._range or (value, value)
        self._range = (min(low, value), max(high, value))
        self._record_shape(*classify_number(value, id_key=self._id_key))
        self._sample(value, None)

    def _observe_string(self, value: str) -> None:
        self._types.add(JsonType.STRING)
        self._extend_length(len(value))
        shape, formats = classify_string(value, id_key=self._id_key)
        self._record_shape(shape, formats)
        self._sample(value, shape)

    def _record_shape(self, shape: Shape, formats: frozenset[str]) -> None:
        self._shapes[shape] += 1
        if formats:
            self._fits[shape][formats] += 1

    def _extend_length(self, size: int) -> None:
        low, high = self._length or (size, size)
        self._length = (min(low, size), max(high, size))

    def _sample(self, value: Scalar, shape: Shape | None) -> None:
        if len(self._samples) < self._max_samples:
            self._samples.setdefault((type(value), value), (value, shape))

    # --- building ----------------------------------------------------------------------------

    def build(
        self, options: Options, warnings: list[ParseWarning], *, count: int | None = None
    ) -> DataNode:
        """The frozen node for this position and its subtree. Document warnings are appended to
        ``warnings``; ``count`` is the parent's denominator (defaults to the values observed).
        """
        shape = self._dominant_shape(options.shape_threshold)
        fmt, formats, ambiguous = resolve_format(self._fits.get(shape) if shape else None)
        if ambiguous:
            warnings.append(ParseWarning(code="ambiguous_date_order", path=self.path))
        if ITEMS in self._properties:
            warnings.append(
                ParseWarning(
                    code="reserved_name",
                    message="an object key named '[]' shares its path with array items",
                    path=join(self.path, ITEMS),
                )
            )
        return DataNode(
            name=self.name,
            path=self.path,
            type=self._type(),
            shape=shape,
            format=fmt,
            formats=formats,
            length=MinMax(*self._length) if self._length else None,
            range=MinMax(*self._range) if self._range and options.samples else None,
            stats=Stats(
                count=self._present if count is None else count,
                present=self._present,
                null=self._nulls,
            ),
            shapes=dict(self._shapes),
            properties=(
                {
                    key: child.build(options, warnings, count=self._objects)
                    for key, child in self._properties.items()
                }
                if self._properties
                else None
            ),
            items=self._items.build(options, warnings) if self._items else None,
            samples=(
                build_samples(list(self._samples.values()), options.masked_shapes)
                if options.samples
                else None
            ),
        )

    def _type(self) -> JsonType | tuple[JsonType, ...]:
        return type_union(self._types)

    def _dominant_shape(self, threshold: float) -> Shape | None:
        return dominant_shape(self._shapes, threshold)


def type_union(types: set[JsonType]) -> JsonType | tuple[JsonType, ...]:
    """A single type, or the sorted union; ``integer`` + ``number`` → ``number`` (spec 3.4)."""
    if JsonType.NUMBER in types:
        types = types - {JsonType.INTEGER}
    ordered = tuple(sorted(types))
    return ordered[0] if len(ordered) == 1 else ordered


def dominant_shape(shapes: Counter[Shape], threshold: float) -> Shape | None:
    """The shape of ≥ ``threshold`` of the non-empty values, else ``mixed`` (spec 3.4)."""
    total = shapes.total()
    if not total:
        return None
    non_empty = total - shapes[Shape.EMPTY]
    if not non_empty:
        return Shape.EMPTY
    top, top_count = next(
        (shape, n) for shape, n in shapes.most_common() if shape is not Shape.EMPTY
    )
    return top if top_count / non_empty >= threshold else Shape.MIXED


def data_fields(node: DataNode) -> dict[str, Any]:
    """The schema fields of ``node``, for building a ``FileNode`` that carries them inline."""
    fields = msgspec.structs.asdict(node)
    del fields["name"], fields["path"], fields["keys"]
    return fields
