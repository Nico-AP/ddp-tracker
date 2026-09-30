"""M4, comparing platforms: which concepts each one discloses, and how people get at their data.

The matrix comes from the concepts (``concepts.py``). The facts per platform below are
fictional, written to look plausible: the page says so, and nobody should quote them.
"""

from dataclasses import dataclass
from operator import attrgetter
from typing import Any

from django.db.models import Max
from django.http import HttpRequest, HttpResponse

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup
from ddp_tracker.journeys.mockups.concepts import CONCEPTS


@dataclass(frozen=True)
class PlatformFacts:
    slug: str
    request_modes: tuple[str, ...]  # how people can request their data, joined into one line
    formats: tuple[str, ...]  # the formats they can choose
    delivery: str  # how long it takes
    documentation: str  # does the platform document its package?
    machine_readable: str
    # the gap between the platform's documentation and what uploads show (fictional counts)
    documented_not_observed: int
    observed_not_documented: int


FACTS: tuple[PlatformFacts, ...] = (
    PlatformFacts(
        slug="tiktok",
        request_modes=("In the app", "in the browser", "Portability API"),
        formats=("JSON", "TXT"),
        delivery="Up to 4 days",
        documentation="Partial: a help page lists the sections, not the fields",
        machine_readable="Yes, if JSON is chosen",
        documented_not_observed=6,
        observed_not_documented=14,
    ),
    PlatformFacts(
        slug="instagram",
        request_modes=("In the app", "in the browser", "Portability API"),
        formats=("JSON", "HTML"),
        delivery="Up to 48 hours",
        documentation="Partial: descriptions for some files",
        machine_readable="Yes, if JSON is chosen (the default is HTML)",
        documented_not_observed=9,
        observed_not_documented=21,
    ),
    PlatformFacts(
        slug="facebook",
        request_modes=("In the app", "in the browser", "Portability API"),
        formats=("JSON", "HTML"),
        delivery="Up to 48 hours",
        documentation="Partial: descriptions for some files",
        machine_readable="Yes, if JSON is chosen (the default is HTML)",
        documented_not_observed=12,
        observed_not_documented=25,
    ),
    PlatformFacts(
        slug="youtube",
        request_modes=("In the browser (Google Takeout)", "Portability API"),
        formats=("JSON", "HTML", "CSV"),
        delivery="Minutes to hours",
        documentation="Partial: a help page per product",
        machine_readable="Partly: the watch history is HTML unless JSON is chosen",
        documented_not_observed=4,
        observed_not_documented=9,
    ),
)

# --- view -------------------------------------------------------------------------------------


def _figures(platform: Platform) -> dict[str, Any]:
    """What this tracker holds about a platform (only uploads that count)."""
    registered = platform.uploads.filter(registered_at__isnull=False)
    points = platform.locations.filter(
        observations__is_data_point=True, observations__upload__registered_at__isnull=False
    )
    return {
        "uploads": registered.count(),
        "data_points": points.distinct().count(),
        "annotations": platform.annotations.count(),
        "last_requested": registered.aggregate(last=Max("requested_at"))["last"],
    }


def compare(request: HttpRequest) -> HttpResponse:
    """M4: concepts by platforms, and how people get at their data on each."""
    concepts = sorted(CONCEPTS, key=attrgetter("name"))
    matrix = [
        (concept, [slug in concept.platforms for slug in DEMO_PLATFORMS]) for concept in concepts
    ]
    # the matrix's last row: how many concepts each platform discloses, in the columns' order
    disclosed = [sum(slug in concept.platforms for concept in CONCEPTS) for slug in DEMO_PLATFORMS]
    panels: list[dict[str, Any]] = []
    for facts in FACTS:
        name, platform = find_platform(facts.slug)
        panels.append(
            {
                "facts": facts,
                "name": name,
                "platform": platform,
                "disclosed": sum(facts.slug in concept.platforms for concept in CONCEPTS),
                "figures": _figures(platform) if platform is not None else None,
            }
        )
    context = {
        "platforms": DEMO_PLATFORMS,
        "matrix": matrix,
        "disclosed": disclosed,
        "panels": panels,
        "total": len(CONCEPTS),
        "has_data": any(panel["platform"] is not None for panel in panels),
        # platforms in this database without a package that counts yet: their "No" says little
        "no_package": [
            panel["name"]
            for panel in panels
            if panel["figures"] is not None and panel["figures"]["uploads"] == 0
        ],
    }
    return render_mockup(request, "compare", "journeys/prototype/compare.html", context)
