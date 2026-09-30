"""M4, comparing platforms: which concepts each one discloses, and how people get at their data.

The matrix comes from the concepts (``concepts.py``). The facts per platform below are
fictional, written to look plausible: the page says so, and nobody should quote them.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup


@dataclass(frozen=True)
class PlatformFacts:
    slug: str
    request_modes: tuple[str, ...]  # how people can request their data
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
        request_modes=("In the app", "In the browser", "Portability API"),
        formats=("JSON", "TXT"),
        delivery="Up to 4 days",
        documentation="Partial: a help page lists the sections, not the fields",
        machine_readable="Yes, if JSON is chosen",
        documented_not_observed=6,
        observed_not_documented=14,
    ),
    PlatformFacts(
        slug="instagram",
        request_modes=("In the app", "In the browser", "Portability API"),
        formats=("JSON", "HTML"),
        delivery="Up to 48 hours",
        documentation="Partial: descriptions for some files",
        machine_readable="Yes, if JSON is chosen (the default is HTML)",
        documented_not_observed=9,
        observed_not_documented=21,
    ),
    PlatformFacts(
        slug="facebook",
        request_modes=("In the app", "In the browser", "Portability API"),
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

# --- view (placeholder; task 4.1 replaces it) -----------------------------------------------


def compare(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "compare", "journeys/prototype/placeholder.html")
