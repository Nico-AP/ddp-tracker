"""The review's "To assign" list as a tree (``schemas/tree.py``): an upload's data points, each
row with its suggestions and status (``TriageItem``) and the uploader's own values."""

from dataclasses import dataclass

from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.values import OwnValues, Value
from ddp_tracker.reviews.services import TriageItem, in_file_order
from ddp_tracker.schemas.examples import as_text
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.services import choices
from ddp_tracker.schemas.timeline import new_in
from ddp_tracker.schemas.tree import PREVIEW, Row, Tree, TreeBuilder, places, row_key


@dataclass
class ReviewRow(Row):
    item: TriageItem | None = None  # of ``primary``: its suggestions and status

    @property
    def primary(self) -> Location:
        return self.item.location if self.item else self.locations[-1]


class _Builder(TreeBuilder):
    def __init__(self, upload: Upload, own: OwnValues | None, items: dict[str, TriageItem]) -> None:
        super().__init__(
            {
                o.location.path: o
                for o in upload.observations.filter(is_data_point=True).select_related(
                    "location", "location__annotation"
                )
            }
        )
        self.upload = upload
        self.own = own
        self.items = items
        self._new: set[int] | None = None

    def new(self) -> set[int]:
        if self._new is None:
            self._new = new_in(self.upload)
        return self._new

    def make_row(self, key: str, observations: list[Observation]) -> Row:
        primary = observations[-1]
        return ReviewRow(
            key=key,
            location=observations[0].location,
            observation=observations[0],
            locations=[o.location for o in observations],
            item=self.items.get(primary.location.path) or self._item(primary),
        )

    def _item(self, observation: Observation) -> TriageItem:
        """A data point that isn't among the untriaged ones handed in: a decided one (a list
        above untriaged fields), or a single row built on its own (after a change)."""
        location = observation.location
        open_ = location.annotation_id is None and not location.ignored
        found = choices(observation) if open_ else []
        return TriageItem(observation, found, location.pk in self.new())

    def decorate(self, row: Row, primary: Observation) -> None:
        """The uploader's own values, when there are; else the default summary."""
        values: list[Value] = self.own.values.get(primary.location.path, []) if self.own else []
        if values:
            row.preview = [as_text(value) for value in values[:PREVIEW]]
            row.more = max(len(values) - PREVIEW, 0)
        else:
            super().decorate(row, primary)


def build(
    upload: Upload,
    items: list[TriageItem],
    own: OwnValues | None = None,
    q: str = "",
    *,
    annotated: bool = False,
) -> Tree:
    """The tree of ``items`` (the untriaged data points, in file order). A list is on its row
    even when it is decided itself, as long as fields of its items aren't. With ``annotated``,
    the decided data points are rows too. ``q`` keeps only rows whose name, path or (for the
    uploader) own values contain it, with the rows below them."""
    builder = _Builder(upload, own, {item.location.path: item for item in items})
    everything = in_file_order(list(builder.points.values())) if annotated else items
    for entry in everything:
        builder.row(row_key(entry.location.path))

    def matches(row: Row, query: str) -> bool:
        values = [
            as_text(value)
            for loc in row.locations
            for value in (own.values if own else {}).get(loc.path, [])
        ]
        return any(query in text.casefold() for text in [row.name, row.key, *values])

    return builder.tree(upload.platform_id, upload.file_name, q, matches)


def build_row(
    upload: Upload, location: Location, own: OwnValues | None = None
) -> tuple[Row, str, str]:
    """One row, as it is now (after a change), without the rows below it; and the paths of its
    group and root."""
    builder = _Builder(upload, own, {})
    row = builder.row(row_key(location.path))
    group = next(iter(builder.groups))
    return row, group, places(upload.platform_id, [group], upload.file_name)[group].root
