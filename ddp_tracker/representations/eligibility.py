"""Which locations can have representations, and which can describe one.

The one place to change to open representations to other kinds of locations: for now only a
list's item that is an object (``VideoList/[]`` of ``[{"Date": …, "Link": …}, …]``), including
the items of files whose content is a list (a JSON array, a CSV's rows). Whether a location
qualifies is derived from all of its observations (it isn't stored); a representation it already
has is kept when later uploads change that.
"""

from collections.abc import Iterable

from django.db.models import QuerySet

from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles


def can_have_representation(location: Location, profile: Profile) -> bool:
    """``location`` (with its ``profile`` over all uploads) can have representations."""
    types = set(profile.main_type.split("|")) - {"null"}
    return location.path.endswith(ITEM) and types == {"object"}


def eligible(locations: Iterable[Location]) -> set[int]:
    """The pks of those of ``locations`` that can have representations."""
    items = [location for location in locations if location.path.endswith(ITEM)]
    found = profiles((location.pk for location in items), Observation.objects.all())
    return {
        location.pk for location in items if can_have_representation(location, found[location.pk])
    }


def is_eligible(location: Location) -> bool:
    return location.pk in eligible([location])


def metadata_candidates(anchor: Location) -> QuerySet[Location]:
    """The locations that can describe a representation of ``anchor``: the data points in its
    subtree (``models.is_below``) that aren't ignored."""
    return (
        Location.objects.filter(
            platform=anchor.platform_id,
            path__startswith=f"{anchor.path}/",
            ignored=False,
            observations__is_data_point=True,
        )
        .select_related("annotation")
        .distinct()
        .order_by("path")
    )
