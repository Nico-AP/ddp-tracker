"""What a location looks like across a set of observations: the values seen, how often, when.

Nothing here is stored; profiles are computed per request from whichever observations a view
uses (e.g. those a ``SchemaFilter`` lets through), in two grouped queries.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, Max, Min, QuerySet

from ddp_tracker.schemas.labels import plain_type
from ddp_tracker.schemas.models import Location, Observation


@dataclass
class Profile:
    kinds: Counter[str] = field(default_factory=Counter)  # value → number of uploads
    types: Counter[str] = field(default_factory=Counter)
    shapes: Counter[str] = field(default_factory=Counter)
    formats: Counter[str] = field(default_factory=Counter)
    uploads: int = 0
    first_seen: date | None = None
    last_seen: date | None = None
    is_data_point: bool = False  # open for annotation in at least one of the observations
    path: str = ""
    item_types: Counter[str] = field(default_factory=Counter)  # types of a list's items
    has_children: bool = False  # in the same observations: False for an object always seen empty

    @property
    def is_list(self) -> bool:
        """Mostly a list in parsed content (shown as ``name[]``); a file that is a list isn't."""
        types = set(self.main_type.split("|")) - {"null"}
        return self.main_kind == "data" and types == {"array"}

    @property
    def label(self) -> str:
        """The main kind and type in plain language ("list of objects", "group of keys")."""
        return plain_type(
            self.main_kind,
            self.main_type,
            self.path,
            _main(self.item_types),
            empty=not self.has_children,
        )

    @property
    def main_kind(self) -> str:
        return _main(self.kinds)

    @property
    def main_type(self) -> str:
        return _main(self.types)

    @property
    def main_shape(self) -> str:
        return _main(self.shapes)

    @property
    def main_format(self) -> str:
        return _main(self.formats)

    @property
    def variants(self) -> int:
        """How many other type / shape / format values than the main ones were observed."""
        return sum(max(len(counter) - 1, 0) for counter in (self.types, self.shapes, self.formats))


def _main(counter: Counter[str]) -> str:
    return counter.most_common(1)[0][0] if counter else ""


def profiles(
    location_ids: Iterable[int], observations: QuerySet[Observation]
) -> dict[int, Profile]:
    """A ``Profile`` per location id, from ``observations`` (only those of these locations)."""
    ids = list(location_ids)
    scoped = observations.filter(location_id__in=ids)
    located = Location.objects.filter(pk__in=ids).values_list("pk", "platform_id", "path")
    result = {location_id: Profile() for location_id in ids}
    for pk, _, path in located:
        result[pk].path = path
    by_path = {(platform_id, path): pk for pk, platform_id, path in located}
    rows = scoped.values(
        "location_id", "kind", "type", "shape", "format", "is_data_point"
    ).annotate(n=Count("id"))

    for row in rows:
        profile = result[row["location_id"]]
        n = row["n"]
        profile.kinds[row["kind"]] += n
        profile.is_data_point = profile.is_data_point or row["is_data_point"]

        for name in ("type", "shape", "format"):
            if row[name]:
                getattr(profile, f"{name}s")[row[name]] += n

    timeline = scoped.values("location_id").annotate(
        uploads=Count("upload", distinct=True),
        first=Min("upload__requested_at"),
        last=Max("upload__requested_at"),
    )

    for seen in timeline:
        profile = result[seen["location_id"]]
        profile.uploads, profile.first_seen, profile.last_seen = (
            seen["uploads"],
            seen["first"],
            seen["last"],
        )

    # the children, in the same observations: whether there were any (an object always seen
    # empty), and what a list's items are (the types of its "[]" child)
    children = (
        observations.filter(
            location__parent_path__in=[path for _, path in by_path],
            location__platform_id__in={platform_id for platform_id, _ in by_path},
        )
        .values("location__platform_id", "location__parent_path", "location__path", "type")
        .annotate(n=Count("id"))
    )
    for child in children:
        key = (child["location__platform_id"], child["location__parent_path"] or "")
        if (parent_id := by_path.get(key)) is None:
            continue
        result[parent_id].has_children = True
        if child["location__path"].endswith("/[]") and child["type"]:
            result[parent_id].item_types[child["type"]] += child["n"]
    return result
