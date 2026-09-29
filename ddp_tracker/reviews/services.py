"""Reviewing an upload: its data points that are new and those known already, what changed, what
is missing, and which of them are still to assign (definitions: docs/docs/tracker/concepts.md)."""

from dataclasses import dataclass
from typing import Any

from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles
from ddp_tracker.schemas.services import Choice, choices
from ddp_tracker.schemas.timeline import FieldChange, change_details, new_in
from ddp_tracker.schemas.tree import row_key


@dataclass(frozen=True)
class TriageItem:
    observation: Observation
    choices: list[Choice]
    is_new: bool  # no earlier-requested upload has the path

    @property
    def location(self) -> Location:
        return self.observation.location

    @property
    def candidate(self) -> dict[str, Any] | None:
        """The best suggestion ``{path, reason, score}``, annotated or not."""
        suggestions = self.observation.suggestions
        return suggestions[0] if suggestions else None

    @property
    def status(self) -> str:
        """``moved`` / ``renamed`` (a suggestion), ``new`` (no earlier upload has the path) or
        ``seen`` (earlier uploads had it, but it was never annotated)."""
        if self.candidate is not None:
            return str(self.candidate["reason"])
        return "new" if self.is_new else "seen"


@dataclass(frozen=True)
class ChangedItem:
    observation: Observation
    diffs: list[FieldChange]  # each field with a value no earlier upload had, and what they had

    @property
    def fields(self) -> list[str]:
        return [diff.field for diff in self.diffs]


@dataclass(frozen=True)
class MissingItem:
    location: Location
    profile: Profile  # over all uploads: how often and until when it was seen


@dataclass(frozen=True)
class Review:
    triage: list[TriageItem]  # untriaged data points of this upload, grouped by parent
    changed: list[ChangedItem]
    missing: list[MissingItem]  # locations of annotations this upload has nowhere (unless moved)


def in_file_order(found: list[Observation]) -> list[Observation]:
    """Depth first, siblings in file order (as the explorer's tree shows them)."""
    if not found:
        return found
    ancestors: set[str] = set()
    for observation in found:
        parts = observation.location.path.split("/")
        ancestors.update("/".join(parts[:end]) for end in range(2, len(parts) + 1))
    positions = dict(
        Location.objects.filter(
            platform=found[0].location.platform_id, path__in=ancestors
        ).values_list("path", "position")
    )

    def key(observation: Observation) -> tuple[tuple[int, str], ...]:
        parts = observation.location.path.split("/")
        prefixes = ["/".join(parts[:end]) for end in range(2, len(parts) + 1)]
        return tuple((positions.get(prefix, 0), prefix) for prefix in prefixes)

    return sorted(found, key=key)


def _untriaged(upload: Upload) -> list[Observation]:
    """The upload's data points without an annotation (and not ignored), in file order."""
    return in_file_order(
        list(
            upload.observations.select_related("location", "location__annotation").filter(
                is_data_point=True, location__annotation__isnull=True, location__ignored=False
            )
        )
    )


NEW, KNOWN = "new", "known"


def scopes(upload: Upload) -> dict[str, set[int]]:
    """The location ids of the upload's data points per tab: **new** (no earlier-requested
    upload has the path) and **known** (earlier ones had it, and nothing changed). Changed data
    points are the Changed tab's only."""
    points = set(
        upload.observations.filter(is_data_point=True).values_list("location_id", flat=True)
    )
    new = new_in(upload) & points
    return {NEW: new, KNOWN: points - new - set(change_details(upload))}


def row_count(upload: Upload, scope: set[int]) -> int:
    """The rows ``scope`` makes in the tree: a list and its item share one."""
    paths = Location.objects.filter(pk__in=scope).values_list("path", flat=True)
    return len({row_key(path) for path in paths})


def triage_items(upload: Upload) -> list[TriageItem]:
    """Only the "To assign" part of ``review``: cheaper, for reloading one row's counts."""
    new = new_in(upload)
    return [TriageItem(o, choices(o), o.location_id in new) for o in _untriaged(upload)]


def review(upload: Upload) -> Review:
    """What a curator needs to look at for ``upload`` (definitions: docs/tracker/concepts.md)."""
    observations = upload.observations.select_related("location", "location__annotation")
    new = new_in(upload)
    untriaged = _untriaged(upload)
    changes = change_details(upload)
    present = set(upload.observations.values_list("location__path", flat=True))
    # an annotated path that a data point here likely matches (at another path or under another
    # key name) isn't missing: it appears once, as that data point's "likely matches …"
    moved_from = {o.suggestions[0]["path"] for o in untriaged if o.suggestions}
    missing = [
        location
        for location in upload.platform.locations.filter(annotation__isnull=False)
        .exclude(annotation__locations__observations__upload=upload)
        .select_related("annotation")
        .order_by("path")
        # a list's item is absent when the list is empty: not missing, just no items this time
        if not (location.path.endswith(ITEM) and location.parent_path in present)
        and location.path not in moved_from
    ]
    seen = profiles(
        (location.pk for location in missing),
        Observation.objects.filter(upload__registered_at__isnull=False),
    )
    return Review(
        triage=[TriageItem(o, choices(o), o.location_id in new) for o in untriaged],
        changed=[
            ChangedItem(o, changes[o.location_id])
            for o in observations.filter(location_id__in=changes).order_by("location__path")
        ],
        missing=[MissingItem(location, seen[location.pk]) for location in missing],
    )
