"""What a location looks like across a set of observations: the values seen, how often, when.

Nothing here is stored; profiles are computed per request from whichever observations a view
uses (e.g. those a ``SchemaFilter`` lets through), in two grouped queries.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, Max, Min, QuerySet

from ddp_tracker.schemas.models import Observation


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
    result = {location_id: Profile() for location_id in ids}
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
    return result
