"""Data points as a tree: grouped by file (the roots), then under the key chains that need no
annotation, lists with their items' fields below them. The review of an upload
(``reviews/tree.py``) and the platform explorer (``schemas/explorer.py``) both show it.

- A **root** is a file (``/user_data.json``); data points that are files themselves (a file
  whose content is a list, media files) have their folder as root.
- A **group** is the nearest ancestor that isn't a data point (a plain object, a file, a folder):
  ``/user_data.json/Ads and data/Off TikTok Activity``, shown as its crumbs.
- A **row** is one data point, except that a list and its item (``VideoList`` and
  ``VideoList/[]``) share one row: it is annotated item first (the item carries the meaning),
  then the list (its name prefilled as "List of …"); it is done when both are.
- The fields of a list's items are rows below the list's row (``depth`` 1, 2 … for lists in
  lists), named by their path within the item (``Meta/Id`` reads ``Meta`` then ``Id``).
- **Muted** rows (the explorer's) are nodes that are never data points but hold something
  themselves: an unparsed file, an object always seen empty.
"""

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ddp_tracker.schemas.models import Location, Observation

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
    observation: Observation  # the representative one (what the row's type says)
    locations: list[Location]  # annotated together: the list and its item, or the one
    depth: int = 0
    children: list["Row"] = field(default_factory=list)
    preview: list[str] = field(default_factory=list)  # values to show (own values, examples)
    more: int = 0  # values not in the preview
    summary: str = ""  # "3 items", or a format, when there are no values to show
    muted: bool = False  # not a data point: shown for completeness, never counted

    @property
    def primary(self) -> Location:
        """What "Add annotation" opens: for a list its item, which carries the meaning."""
        return self.locations[-1]

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
    def is_open(self) -> bool:
        """Still to annotate (muted rows never are)."""
        return not self.muted and not self.decided

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
        return sum(row.is_open for top in self.rows for row in top.walk())

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


class TreeBuilder:
    """Rows placed under their list or group, each made on first use. ``points`` are the data
    points' representative observations by path. Subclasses decide what a row carries
    (``make_row``) and shows (``decorate``)."""

    def __init__(self, points: dict[str, Observation]) -> None:
        self.points = points
        self.rows: dict[str, Row] = {}
        self.groups: dict[str, Group] = {}

    def make_row(self, key: str, observations: list[Observation]) -> Row:
        return Row(
            key=key,
            location=observations[0].location,
            observation=observations[0],
            locations=[o.location for o in observations],
        )

    def decorate(self, row: Row, primary: Observation) -> None:
        """The row's preview; by default the number of items of a list, else the format."""
        if row.is_list:
            count = (primary.details.get("stats") or {}).get("present", 0)
            row.summary = f"{count} item{'' if count == 1 else 's'}"
        else:
            row.summary = row.observation.format

    def row(self, key: str) -> Row:
        """The row of ``key``, made (and placed under its list or group) on first use."""
        if key in self.rows:
            return self.rows[key]
        paths = [key]
        while paths[-1] + ITEMS in self.points:
            paths.append(paths[-1] + ITEMS)
        observations = [self.points[path] for path in paths if path in self.points]
        row = self.make_row(key, observations)
        self.decorate(row, observations[-1])
        self._place(row)
        return row

    def muted(self, observation: Observation) -> Row:
        """A node that is never a data point, as a row of its own (not counted)."""
        key = observation.location.path
        row = Row(key, observation.location, observation, [observation.location], muted=True)
        self._place(row)
        return row

    def _place(self, row: Row) -> None:
        self.rows[row.key] = row
        within = enclosing_list(row.key)
        if within is not None and within in self.points:
            parent = self.row(within)
            row.depth = parent.depth + 1
            parent.children.append(row)
        else:
            group_path = row.location.parent_path or ""
            if group_path not in self.groups:
                self.groups[group_path] = Group(group_path, [])
            self.groups[group_path].rows.append(row)

    def tree(
        self,
        platform_id: int,
        root_name: str,
        q: str = "",
        matches: Callable[[Row, str], bool] | None = None,
        *,
        by_open: bool = True,
    ) -> Tree:
        """The groups under their roots; with ``q``, only the rows ``matches`` (by default: name
        or path contain it), with the rows below them, all expanded. ``by_open``: start where
        something is still to annotate (the review), else at the very first (the explorer)."""
        groups = list(self.groups.values())
        found = places(platform_id, [group.path for group in groups], root_name)
        if q:
            groups = filtered(groups, q.casefold(), matches or _name_or_path)
        return Tree(open_first(_rooted(groups, found), everything=bool(q), by_open=by_open))


def _name_or_path(row: Row, q: str) -> bool:
    return q in row.name.casefold() or q in row.key.casefold()


def filtered(groups: list[Group], q: str, matches: Callable[[Row, str], bool]) -> list[Group]:
    """The groups' rows that match ``q`` (casefolded), with everything below them; a list stays
    when a row below it matches."""

    def keep(row: Row) -> Row | None:
        if matches(row, q):
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


def places(platform_id: int, paths: list[str], root_name: str) -> dict[str, Place]:
    """Each group path's place. The root is the deepest file among the path's prefixes (the
    path itself included); in a single-file upload the file is the top level itself (its first
    level holds keys, where a zip's holds files and folders), titled ``root_name``; without
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
        found[path] = Place(root, _title(root, root_name, kinds), _crumbs(below, kinds))
    return found


def _title(root: str, root_name: str, kinds: dict[str, set[str]]) -> list[tuple[str, bool]]:
    if not root:
        return [(root_name, True)]
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


def open_first(roots: list[Root], *, everything: bool = False, by_open: bool = True) -> list[Root]:
    """Expand only where to start: the first root with something open, and its first such
    group (else, or without ``by_open``, the very first ones); with ``everything`` (a filter's
    matches), all of them."""
    for root in roots:
        root.is_open = everything
        for group in root.groups:
            group.is_open = everything
    if everything or not roots:
        return roots
    root = next((r for r in roots if by_open and r.open_count), roots[0])
    root.is_open = True
    if root.groups:
        next((g for g in root.groups if by_open and g.open_count), root.groups[0]).is_open = True
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
    platform_id: int, entries: Sequence[tuple[Location, object]], root_name: str
) -> list[Root]:
    """``entries`` (a location and what to show about it) grouped by parent, under their
    roots, in order."""
    found: dict[str, Section] = {}
    for location, entry in entries:
        path = location.parent_path or ""
        found.setdefault(path, Section(path, [])).entries.append(entry)
    return open_first(_rooted(list(found.values()), places(platform_id, list(found), root_name)))
