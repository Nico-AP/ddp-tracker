"""M5, the changelog of a platform: what it added, moved, changed and removed from one request
to the next. Computed from the observations of the platform's registered uploads, so with the
demo data (two TikTok packages, six months apart) it is real.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup
from ddp_tracker.schemas.timeline import change_details, new_in


@dataclass(frozen=True)
class Change:
    path: str
    field: str  # kind, type, shape or format
    before: str  # what earlier requests had
    now: str


@dataclass(frozen=True)
class Entry:
    """One request of the platform, compared with the ones requested before it."""

    upload: Upload
    first: bool  # nothing earlier to compare with
    data_points: int
    added: list[str]  # new, and unlike anything earlier
    moved: list[tuple[str, str]]  # (the earlier path, the path now)
    changed: list[Change]
    removed: list[str]  # in the request before, gone now, and not moved

    @property
    def summary(self) -> str:
        """What changed, in words: only what occurred, for example "5 added, 1 removed"."""
        counts = (
            (len(self.added), "added"),
            (len(self.moved), "moved or renamed"),
            (len(self.changed), "changed"),
            (len(self.removed), "removed"),
        )
        return ", ".join(f"{count} {label}" for count, label in counts if count)


def timeline(platform: Platform) -> list[Entry]:
    """The platform's uploads that count, newest request first, each with what changed since
    the requests before it. "New" and "changed" are the review's (``schemas/timeline.py``): they
    compare with uploads requested strictly earlier. Moves come shallowest first, the other
    lists in the order of their paths."""
    uploads = list(
        platform.uploads.filter(registered_at__isnull=False).order_by("requested_at", "pk")
    )
    entries = []
    for upload in uploads:
        observations = list(
            upload.observations.filter(is_data_point=True).select_related("location")
        )
        paths = {observation.location_id: observation.location.path for observation in observations}
        earlier = [other for other in uploads if other.requested_at < upload.requested_at]
        if not earlier:
            entries.append(
                Entry(
                    upload=upload,
                    first=True,
                    data_points=len(paths),
                    added=[],
                    moved=[],
                    changed=[],
                    removed=[],
                )
            )
            continue
        new = new_in(upload)
        fresh = [observation for observation in observations if observation.location_id in new]
        # the shallowest first, so that a whole list comes before its fields
        moved = sorted(
            (
                (observation.suggestions[0]["path"], observation.location.path)
                for observation in fresh
                if observation.suggestions
            ),
            key=lambda pair: (pair[0].count("/"), pair),
        )
        added = sorted(o.location.path for o in fresh if not o.suggestions)
        changed = sorted(
            (
                Change(paths[location_id], change.field, ", ".join(change.before), change.now)
                for location_id, found in change_details(upload).items()
                if location_id in paths  # data points only
                for change in found
            ),
            key=lambda change: (change.path, change.field),
        )
        before = set(
            earlier[-1]
            .observations.filter(is_data_point=True)
            .values_list("location__path", flat=True)
        )
        removed = sorted(before - set(paths.values()) - {source for source, _ in moved})
        entries.append(
            Entry(
                upload=upload,
                first=False,
                data_points=len(paths),
                added=added,
                moved=moved,
                changed=changed,
                removed=removed,
            )
        )
    return entries[::-1]


def changes(request: HttpRequest, slug: str) -> HttpResponse:
    """M5: the changelog of one platform."""
    name, platform = find_platform(slug)
    context = {
        "platform_name": name,
        "platform": platform,
        "entries": timeline(platform) if platform is not None else [],
        "others": [(other, label) for other, label in DEMO_PLATFORMS.items() if other != slug],
    }
    return render_mockup(request, "changes", "journeys/prototype/changes.html", context)
