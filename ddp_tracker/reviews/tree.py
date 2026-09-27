"""The review's "To assign" list as a tree: data points grouped by file (the roots), then under
the key chains that need no annotation, lists with their items' fields below them.

- A **root** is a file (``/user_data.json``); data points that are files themselves (a file
  whose content is a list, media files) have their folder as root.

- A **group** is the nearest ancestor that isn't a data point (a plain object, a file, a folder):
  ``/user_data.json/Ads and data/Off TikTok Activity``, shown as its crumbs.
- A **row** is one data point, except that a list and its item (``VideoList`` and
  ``VideoList/[]``) share one row: it is annotated item first (the item carries the meaning),
  then the list (its name prefilled as "List of …"); it is done when both are.
- The fields of a list's items are rows below the list's row (``depth`` 1, 2 … for lists in
  lists), named by their path within the item (``Meta/Id`` reads ``Meta`` then ``Id``).
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.values import OwnValues, Value
from ddp_tracker.reviews.services import TriageItem, in_file_order
from ddp_tracker.schemas.examples import as_text
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.services import choices
from ddp_tracker.schemas.timeline import new_in

ITEMS = "/[]"
SHAPES = {"datetime", "date", "time", "unix_timestamp", "url", "email", "uuid"}
PREVIEW = 1  # values shown in a row, then "+N"
CHAIN = " \N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK} "  # between the keys of a path


def row_key(path: str) -> str:
    """The path of a data point's row: a list's item (``…/L/[]``) is on its list's row."""
    while path.endswith(ITEMS):
        path = path[: -len(ITEMS)]
    return path


def enclosing_list(key: str) -> str | None:
    """The row of the list whose items ``key`` is in (``/a/L/[]/x`` → ``/a/L``), if any."""
    marker = ITEMS + "/"
    return row_key(key[: key.rindex(marker)]) if marker in key else None


def type_badge(observation: Observation) -> str:
    """``array`` for a list, else a telling shape (``datetime``, ``url`` …), else the JSON type;
    ``?`` when the value can be empty."""
    parts = [part for part in observation.type.split("|") if part]
    types = [part for part in parts if part != "null"]
    optional = "?" if "null" in parts and types else ""
    if types == ["array"]:
        return "array" + optional
    if observation.shape in SHAPES:
        return observation.shape + optional
    return ("|".join(types) or observation.kind) + optional


def group_id(path: str) -> str:
    """A stable HTML id for a group (its path can hold any character)."""
    return "group-" + hashlib.sha1(path.encode(), usedforsecurity=False).hexdigest()[:10]


@dataclass
class Row:
    key: str
    location: Location  # shown (for a list: the list)
    observation: Observation
    locations: list[Location]  # annotated together: the list and its item, or the one
    item: TriageItem  # of ``primary``: its suggestions and status
    depth: int = 0
    children: list["Row"] = field(default_factory=list)
    preview: list[str] = field(default_factory=list)  # the uploader's own values
    more: int = 0  # own values not in the preview
    summary: str = ""  # "3 items", or a format, when there are no own values to show

    @property
    def primary(self) -> Location:
        """What "Add annotation" opens: for a list its item, which carries the meaning."""
        return self.item.location

    @property
    def is_list(self) -> bool:
        return len(self.locations) > 1

    @property
    def name(self) -> str:
        within = enclosing_list(self.key)
        if within is None:
            name = self.location.display_name if self.location.path else "Root"
        else:
            rest = self.key[len(within) + len(ITEMS) + 1 :]
            name = CHAIN.join(rest.split("/"))
        return name + ("[]" if self.is_list else "")

    @property
    def open_location(self) -> Location | None:
        """The next one to annotate: the item first (it carries the meaning), then the list."""
        undecided = [loc for loc in self.locations if loc.annotation_id is None and not loc.ignored]
        return self.primary if self.primary in undecided else next(iter(undecided), None)

    @property
    def type_badge(self) -> str:
        return type_badge(self.observation)

    @property
    def decided(self) -> bool:
        return all(loc.annotation_id is not None or loc.ignored for loc in self.locations)

    @property
    def ignored(self) -> bool:
        return all(loc.ignored for loc in self.locations)

    @property
    def triggers(self) -> str:
        """The htmx events this row reloads on: a change to any of its locations."""
        return ", ".join(f"triaged-{loc.pk} from:body" for loc in self.locations)

    def walk(self) -> list["Row"]:
        return [self, *(row for child in self.children for row in child.walk())]


@dataclass
class Group:
    path: str
    crumbs: list[tuple[str, bool]]  # (name, is a key) — files and folders aren't keys
    rows: list[Row] = field(default_factory=list)
    is_open: bool = False  # expanded on page load (``open_first``)

    @property
    def id(self) -> str:
        return group_id(self.path)

    @property
    def open_count(self) -> int:
        return sum(not row.decided for top in self.rows for row in top.walk())

    def lines(self) -> list[Row]:
        """The rows as they are listed: each one followed by the rows below it."""
        return [row for top in self.rows for row in top.walk()]


@dataclass
class Root:
    """A file (or, for data points that are files themselves, their folder): the tree's top
    level, one collapsible block each, with its groups inside."""

    path: str
    title: list[tuple[str, bool]]  # (name, is the last part): folders muted, the file bold
    groups: list[Any] = field(default_factory=list)  # Group, or Section in Changed/Missing
    is_open: bool = False

    @property
    def id(self) -> str:
        return "root-" + group_id(self.path).removeprefix("group-")

    @property
    def open_count(self) -> int:
        return sum(group.open_count for group in self.groups)


@dataclass
class Tree:
    roots: list[Root]

    @property
    def groups(self) -> list[Group]:
        return [group for root in self.roots for group in root.groups]

    @property
    def open_count(self) -> int:
        return sum(root.open_count for root in self.roots)


class _Builder:
    def __init__(self, upload: Upload, own: OwnValues | None) -> None:
        self.upload = upload
        self.own = own
        self.points = {
            o.location.path: o
            for o in upload.observations.filter(is_data_point=True).select_related(
                "location", "location__annotation"
            )
        }
        self.rows: dict[str, Row] = {}
        self.groups: dict[str, Group] = {}
        self._new: set[int] | None = None

    def new(self) -> set[int]:
        if self._new is None:
            self._new = new_in(self.upload)
        return self._new

    def row(self, key: str, items: dict[str, TriageItem]) -> Row:
        """The row of ``key``, made (and placed under its list or group) on first use."""
        if key in self.rows:
            return self.rows[key]
        paths = [key]
        while paths[-1] + ITEMS in self.points:
            paths.append(paths[-1] + ITEMS)
        observations = [self.points[path] for path in paths if path in self.points]
        primary = observations[-1]
        item = items.get(primary.location.path) or self._item(primary)
        row = Row(
            key=key,
            location=observations[0].location,
            observation=observations[0],
            locations=[o.location for o in observations],
            item=item,
        )
        self._preview(row, primary)
        self.rows[key] = row
        within = enclosing_list(key)
        if within is not None and within in self.points:
            parent = self.row(within, items)
            row.depth = parent.depth + 1
            parent.children.append(row)
        else:
            group_path = observations[0].location.parent_path or ""
            if group_path not in self.groups:
                self.groups[group_path] = Group(group_path, [])
            self.groups[group_path].rows.append(row)
        return row

    def _item(self, observation: Observation) -> TriageItem:
        """A data point that isn't among the untriaged ones handed in: a decided one (a list
        above untriaged fields), or a single row built on its own (after a change)."""
        location = observation.location
        open_ = location.annotation_id is None and not location.ignored
        found = choices(observation) if open_ else []
        return TriageItem(observation, found, location.pk in self.new())

    def _preview(self, row: Row, primary: Observation) -> None:
        values: list[Value] = self.own.values.get(primary.location.path, []) if self.own else []
        if values:
            row.preview = [as_text(value) for value in values[:PREVIEW]]
            row.more = max(len(values) - PREVIEW, 0)
        elif row.is_list:
            count = (primary.details.get("stats") or {}).get("present", 0)
            row.summary = f"{count} item{'' if count == 1 else 's'}"
        else:
            row.summary = row.observation.format


def _prefixes(path: str) -> list[str]:
    """``/a/b`` → ``["/a", "/a/b"]``."""
    parts = path.split("/")
    return ["/".join(parts[: end + 1]) for end in range(1, len(parts))] if path else []


@dataclass(frozen=True)
class Place:
    """Where a group sits: its root, and the keys between the root and the group."""

    root: str
    title: list[tuple[str, bool]]
    crumbs: list[tuple[str, bool]]  # (name, is a key)


def places(platform_id: int, paths: list[str], upload_name: str) -> dict[str, Place]:
    """Each group path's place. The root is the deepest file among the path's prefixes (the
    path itself included); in a single-file upload the file is the top level itself (its first
    level holds keys, where a zip's holds files and folders), titled ``upload_name``; without
    either (data points that are files themselves), the group's folder. A list's item is its
    list's name with ``[]`` (``VideoList[]``), not a crumb of its own.

    Kinds come from all uploads of the platform (the Missing tab's locations aren't in the one
    reviewed), so a path may have had several: a file in one upload is a file.
    """
    prefixes = {prefix for path in paths for prefix in _prefixes(path)}
    kinds: dict[str, set[str]] = {}
    for path, kind in Observation.objects.filter(
        location__platform_id=platform_id, location__path__in=prefixes
    ).values_list("location__path", "kind"):
        kinds.setdefault(path, set()).add(kind)
    found: dict[str, Place] = {}
    for path in paths:
        chain = _prefixes(path)
        files = [i for i, prefix in enumerate(chain) if "file" in kinds.get(prefix, ())]
        if files:
            root, below = chain[files[-1]], chain[files[-1] + 1 :]
        elif not path or "data" in kinds.get(chain[0], ()):  # keys at the top: a single file
            root, below = "", chain
        else:
            root, below = path, []
        found[path] = Place(root, _title(root, upload_name, kinds), _crumbs(below, kinds))
    return found


def _title(root: str, upload_name: str, kinds: dict[str, set[str]]) -> list[tuple[str, bool]]:
    if not root:
        return [(upload_name, True)]
    names = root.split("/")[1:]
    last = names[-1] + ("" if "file" in kinds.get(root, ()) else "/")
    return [*((name, False) for name in names[:-1]), (last, True)]


def _crumbs(chain: list[str], kinds: dict[str, set[str]]) -> list[tuple[str, bool]]:
    names: list[tuple[str, bool]] = []
    for prefix in chain:
        name = prefix.rsplit("/", 1)[-1]
        if name == "[]" and names:
            names[-1] = (names[-1][0] + "[]", names[-1][1])
        else:
            names.append((name, "data" in kinds.get(prefix, ())))
    return names


def open_first(roots: list[Root], *, everything: bool = False) -> list[Root]:
    """Expand only where to start: the first root with something open, and its first such
    group (else the very first ones); with ``everything`` (a filter's matches), all of them."""
    for root in roots:
        root.is_open = everything
        for group in root.groups:
            group.is_open = everything
    if everything or not roots:
        return roots
    root = next((r for r in roots if r.open_count), roots[0])
    root.is_open = True
    if root.groups:
        next((g for g in root.groups if g.open_count), root.groups[0]).is_open = True
    return roots


def _rooted(groups: list[Any], found: dict[str, Place]) -> list[Root]:
    """``groups`` (in order) under their roots (in order of first appearance)."""
    roots: dict[str, Root] = {}
    for group in groups:
        place = found[group.path]
        group.crumbs = place.crumbs
        roots.setdefault(place.root, Root(place.root, place.title)).groups.append(group)
    return list(roots.values())


@dataclass
class Section:
    """A group of the Changed and Missing tabs: locations under the same parent."""

    path: str
    crumbs: list[tuple[str, bool]]
    entries: list[object] = field(default_factory=list)
    is_open: bool = False

    @property
    def open_count(self) -> int:
        return len(self.entries)


def sections(
    platform_id: int, entries: Sequence[tuple[Location, object]], upload_name: str
) -> list[Root]:
    """``entries`` (a location and what to show about it) grouped by parent, under their
    roots, in order."""
    found: dict[str, Section] = {}
    for location, entry in entries:
        path = location.parent_path or ""
        found.setdefault(path, Section(path, [])).entries.append(entry)
    return open_first(_rooted(list(found.values()), places(platform_id, list(found), upload_name)))


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
    builder = _Builder(upload, own)
    by_path = {item.location.path: item for item in items}
    everything = in_file_order(list(builder.points.values())) if annotated else items
    for entry in everything:
        builder.row(row_key(entry.location.path), by_path)
    groups = list(builder.groups.values())
    found = places(upload.platform_id, [group.path for group in groups], upload.file_name)
    if q:
        groups = _filtered(groups, q.casefold(), own)
    return Tree(open_first(_rooted(groups, found), everything=bool(q)))


def build_row(
    upload: Upload, location: Location, own: OwnValues | None = None
) -> tuple[Row, str, str]:
    """One row, as it is now (after a change), without the rows below it; and the paths of its
    group and root."""
    builder = _Builder(upload, own)
    row = builder.row(row_key(location.path), {})
    group = next(iter(builder.groups))
    return row, group, places(upload.platform_id, [group], upload.file_name)[group].root


def _filtered(groups: list[Group], q: str, own: OwnValues | None) -> list[Group]:
    def matches(row: Row) -> bool:
        values = [
            value
            for loc in row.locations
            for value in (own.values if own else {}).get(loc.path, [])
        ]
        texts = [row.name, row.key, *(as_text(value) for value in values)]
        return any(q in text.casefold() for text in texts)

    def keep(row: Row) -> Row | None:
        if matches(row):
            return row  # with everything below it
        children = [kept for child in row.children if (kept := keep(child)) is not None]
        if not children:
            return None
        row.children = children
        return row

    kept_groups = []
    for group in groups:
        group.rows = [kept for row in group.rows if (kept := keep(row)) is not None]
        if group.rows:
            kept_groups.append(group)
    return kept_groups
