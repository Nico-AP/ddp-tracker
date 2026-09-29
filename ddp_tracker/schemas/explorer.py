"""The platform explorer's tree (``schemas/tree.py``): the data points of the uploads a
``SchemaFilter`` lets through (one request and root format), with nodes that are never data points but hold
something themselves (an unparsed file, an object always seen empty) as muted rows."""

from collections.abc import Callable

from ddp_tracker.ddps.models import Platform
from ddp_tracker.representations.eligibility import eligible
from ddp_tracker.schemas.examples import preview
from ddp_tracker.schemas.filters import SchemaFilter, format_label
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.tree import PREVIEW, Row, Tree, TreeBuilder, places, row_key


class _Builder(TreeBuilder):
    def decorate(self, row: Row, primary: Observation) -> None:
        """The data point's examples (its item's, for a list of values), else the default."""
        shown, more = preview(primary.location, PREVIEW)
        if shown:
            row.preview, row.more = shown, more
        else:
            super().decorate(row, primary)


def _latest(observations: list[Observation]) -> dict[str, Observation]:
    """One observation per location: the latest-requested upload's."""
    found: dict[str, Observation] = {}
    for observation in observations:  # ordered latest first
        found.setdefault(observation.location.path, observation)
    return found


def _observations(platform: Platform, schema_filter: SchemaFilter) -> list[Observation]:
    return list(
        schema_filter.observations(platform)
        .select_related("location", "location__annotation")
        .order_by("-upload__requested_at", "-upload_id")
    )


def _alphabetical_key(path: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """A path's segments ignoring case, then as spelled: paths that differ only in case (TikTok
    renamed ``TikTok Live`` to ``Tiktok Live``) sit right next to each other, at every level.
    Depth first: a path's children follow it."""
    segments = tuple(path.split("/"))
    return tuple(segment.casefold() for segment in segments), segments


def _alphabetical(points: list[Observation]) -> list[Observation]:
    """The explorer's order: alphabetical, ignoring case. Positions in a file differ between uploads, so
    the review's file order isn't defined across them."""
    return sorted(points, key=lambda observation: _alphabetical_key(observation.location.path))


# What the explorer shows (its selector): everything, or only what still lacks something
SHOW_ALL, MISSING_ANNOTATIONS, MISSING_REPRESENTATIONS = "all", "annotations", "representations"
SHOW = (SHOW_ALL, MISSING_ANNOTATIONS, MISSING_REPRESENTATIONS)


def explorer_tree(
    platform: Platform, schema_filter: SchemaFilter, q: str = "", *, show: str = SHOW_ALL
) -> Tree:
    """The tree of the filtered uploads' data points. ``show``: all of them, only those without
    an annotation, or only those that could have a representation but have none (``SHOW``).
    ``q`` keeps the rows whose name or path contain it."""
    latest = _latest(_observations(platform, schema_filter))
    points = {path: o for path, o in latest.items() if o.is_data_point}
    builder = _Builder(points)
    parents = {o.location.parent_path for o in latest.values()}
    everything = _alphabetical(list(latest.values()))
    for observation in everything:
        if observation.is_data_point:
            builder.row(row_key(observation.location.path))
        elif _is_muted(observation, parents):
            builder.muted(observation)
    if show == MISSING_ANNOTATIONS:
        _keep_only(builder, lambda row: row.is_open)
    elif show == MISSING_REPRESENTATIONS:
        unrepresented = _unrepresented(platform)
        _keep_only(builder, lambda row: not row.muted and row.primary.pk in unrepresented)
    # groups alphabetical too (by their first row, "A/B" would come before "A"'s own rows)
    builder.groups = dict(
        sorted(builder.groups.items(), key=lambda item: _alphabetical_key(item[0]))
    )
    return builder.tree(platform.pk, _root_name(schema_filter), q, by_open=False)


def _root_name(schema_filter: SchemaFilter) -> str:
    """A single file's tree has no upload name of its own: its format's ("JSON file")."""
    return format_label(schema_filter.root_format) if schema_filter.root_format else "Root"


def _is_muted(observation: Observation, parents: set[str | None]) -> bool:
    """Never a data point, but something of its own: an unparsed file, an object never seen
    with keys (not a folder, the root or a key that only groups others)."""
    if observation.location.path in parents or not observation.location.path:
        return False
    return observation.kind in {"unmatched", "file"} or (
        observation.kind == "data" and "object" in observation.type
    )


def _unrepresented(platform: Platform) -> set[int]:
    """The platform's locations that can have a representation (a list's item, the row's
    primary location) but have none."""
    items = platform.locations.filter(path__endswith=ITEM, representations__isnull=True)
    return eligible(items)


def _keep_only(builder: TreeBuilder, wanted: Callable[[Row], bool]) -> None:
    """Only the ``wanted`` rows; a list stays while rows below it are wanted."""

    def keep(row: Row) -> Row | None:
        row.children = [kept for child in row.children if (kept := keep(child)) is not None]
        return row if wanted(row) or row.children else None

    for path, group in list(builder.groups.items()):
        group.rows = [kept for row in group.rows if (kept := keep(row)) is not None]
        if not group.rows:
            del builder.groups[path]


def build_row(
    platform: Platform, schema_filter: SchemaFilter, location: Location
) -> tuple[Row, str, str]:
    """One row, as it is now (after a change), without the rows below it; and the paths of its
    group and root."""
    latest = _latest(_observations(platform, schema_filter))
    builder = _Builder({path: o for path, o in latest.items() if o.is_data_point})
    row = builder.row(row_key(location.path))
    builder.mark_pending()
    group = next(iter(builder.groups))
    return row, group, places(platform.pk, [group], _root_name(schema_filter))[group].root
