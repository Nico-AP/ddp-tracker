""" "New" and "changed", as defined in docs/docs/tracker/concepts.md.

Both compare an upload with the uploads of its platform requested *strictly earlier*: the order
of request dates, never the order in which uploads happened to be registered.
"""

from collections import defaultdict

from ddp_parser.model import JsonType
from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.models import Observation

FIELDS = ("kind", "type", "shape", "format")
_UNSTABLE_SHAPES = frozenset({"mixed", "empty"})


def normalized(field: str, value: str) -> str:
    """The comparable form of a value; "" means "ignored" (data-dependent noise)."""
    if field == "type":
        return "|".join(sorted(t for t in value.split("|") if t and t != JsonType.NULL))
    if field == "shape" and value in _UNSTABLE_SHAPES:
        return ""
    return value


def _earlier(upload: Upload) -> dict[int, dict[str, set[str]]]:
    """For each location of ``upload``: the values each field had in earlier-requested uploads."""
    rows = (
        Observation.objects.filter(
            upload__platform_id=upload.platform_id,
            upload__registered_at__isnull=False,
            upload__requested_at__lt=upload.requested_at,
            location__observations__upload=upload,
        )
        .values_list("location_id", *FIELDS)
        .distinct()
    )
    seen: defaultdict[int, dict[str, set[str]]] = defaultdict(
        lambda: {name: set() for name in FIELDS}
    )
    for location_id, *values in rows:
        for name, value in zip(FIELDS, values, strict=True):
            seen[location_id][name].add(normalized(name, value))
    return seen


def new_in(upload: Upload) -> set[int]:
    """Location ids of ``upload`` that no earlier-requested upload has."""
    earlier = _earlier(upload)
    return {
        lid
        for lid in upload.observations.values_list("location_id", flat=True)
        if lid not in earlier
    }


def changes_in(upload: Upload) -> dict[int, list[str]]:
    """Location id → fields whose value in ``upload`` no earlier-requested upload had.

    Locations that are new in ``upload`` have no changes; ignored values never count.
    """
    earlier = _earlier(upload)
    changes: dict[int, list[str]] = {}
    for observation in upload.observations.values("location_id", *FIELDS):
        before = earlier.get(observation["location_id"])
        if before is None:
            continue
        fields = [
            name
            for name in FIELDS
            if (value := normalized(name, observation[name])) and value not in before[name]
        ]
        if fields:
            changes[observation["location_id"]] = fields
    return changes
