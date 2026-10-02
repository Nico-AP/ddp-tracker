"""Mock-up pages for features that do not exist yet: real pages with fictional data and a banner,
so that nobody mistakes them for working features. Each page has a module here (its fictional
data and its view); ``MOCKUPS`` describes them all, for the page frame and the tests.
"""

from dataclasses import dataclass
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.content import ROLES, Role

# the platforms the demo data has (demo/spec.py): mock-ups know their names before seed_demo ran
DEMO_PLATFORMS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
}


@dataclass(frozen=True)
class Mockup:
    key: str
    number: str  # M1 … M12, as in the site structure
    title: str
    lead: str
    url_names: tuple[str, ...]  # the URL names that belong to this page
    feature: str  # the planned feature, in words
    section: str  # its section in the features analysis
    hackathon: str = ""  # the hackathon note it illustrates


MOCKUPS: dict[str, Mockup] = {
    mockup.key: mockup
    for mockup in (
        Mockup(
            key="concepts",
            number="M1",
            title="Concepts",
            lead=(
                "What people do on platforms, as concepts that mean the same everywhere: "
                "pick your research field and theme, and see which platforms provide what."
            ),
            url_names=("journeys:concepts",),
            feature="a concept view for researchers, with labels per research field",
            section="4.1",
            hackathon=(
                "Field-specific top-level ontology; sorting of data point lists according to "
                "most used or relevant; default public page versus community page."
            ),
        ),
        Mockup(
            key="concept",
            number="M2",
            title="Concept",
            lead="What one concept means, and where and how each platform provides it.",
            url_names=("journeys:concept",),
            feature="a concept's detail: meaning, availability, time zone, examples as a table",
            section="4.1",
            hackathon=(
                "Clarity on what the captured time represents (tz_whos); example values as a "
                "table with title and value; translations for fields."
            ),
        ),
        Mockup(
            key="shortlist",
            number="M3",
            title="Study shortlist",
            lead=(
                "The concepts a study needs, with their exact paths: built by the researcher, "
                "handed to the engineer, and downloaded as a codebook or an extraction "
                "specification."
            ),
            url_names=(
                "journeys:shortlist",
                "journeys:shortlist-add",
                "journeys:shortlist-remove",
                "journeys:shortlist-clear",
                "journeys:shortlist-codebook",
                "journeys:shortlist-blueprint",
            ),
            feature="a study shortlist with codebook and DDM File Blueprint exports",
            section="4.1 and 4.2",
            hackathon="Prioritised research and engineering perspective and needs.",
        ),
        Mockup(
            key="compare",
            number="M4",
            title="Compare platforms",
            lead="What each platform discloses, side by side.",
            url_names=("journeys:compare",),
            feature="a comparison of platforms on disclosure",
            section="4.3",
            hackathon="Gaps between platform schema documentation and actual DDPs.",
        ),
        Mockup(
            key="changes",
            number="M5",
            title="Changelog",
            lead="What a platform added, moved, changed and removed from one request to the next.",
            url_names=("journeys:changes",),
            feature="a changelog per platform",
            section="4.2 and 4.3",
        ),
        Mockup(
            key="api",
            number="M6",
            title="API",
            lead="Read the tracker's knowledge from a script, another tool or a language model.",
            url_names=("journeys:api",),
            feature="a read-only API with exports and access for LLMs",
            section="4.7",
            hackathon=(
                "API endpoints for researchers and LLMs; annotations as explainers for "
                "participants."
            ),
        ),
        Mockup(
            key="snapshots",
            number="M7",
            title="Snapshots",
            lead="Dated releases of the knowledge base that a paper or a report can cite.",
            url_names=("journeys:snapshots",),
            feature="versioned, citable snapshots and a licence",
            section="4.1, 4.3 and 4.7",
            hackathon="Referencable archive.",
        ),
        Mockup(
            key="request",
            number="M8",
            title="Request your data",
            lead="How to ask a platform for your data download package, step by step.",
            url_names=("journeys:request",),
            feature="platform-specific instructions for requesting a DDP",
            section="4.4",
            hackathon="Incentive to add new DDPs; paired donation sets.",
        ),
        Mockup(
            key="moderate",
            number="M9",
            title="Moderator dashboard",
            lead="What waits for you on the platforms you moderate.",
            url_names=("journeys:moderate",),
            feature="a moderator role for one or more platforms, with its own dashboard",
            section="4.5",
            hackathon=(
                "DDP hubs responsible for single platforms and assigning moderators; "
                "prioritise annotations that are actually important; crowdsource annotation "
                "questions."
            ),
        ),
        Mockup(
            key="seed",
            number="M10",
            title="Seed annotations",
            lead=(
                "Start from what exists already, and check it, instead of writing every "
                "annotation by hand."
            ),
            url_names=("journeys:seed",),
            feature="seeding annotations from documentation, paired uploads and AI suggestions",
            section="4.5",
            hackathon=(
                "Integrate platform documentation as a starting point to seed annotations; "
                "pairing of HTML and JSON; AI-flagged labels, checked with time."
            ),
        ),
        Mockup(
            key="roles",
            number="M11",
            title="Roles and platforms",
            lead="Who may do what, and on which platform, without the Django admin.",
            url_names=("journeys:roles",),
            feature="role and platform management outside the Django admin",
            section="4.6",
            hackathon="Governance: hubs per platform, working groups per platform.",
        ),
        Mockup(
            key="learn",
            number="M12",
            title="What a platform keeps about you",
            lead="A plain summary of a platform's data download package, and a short exercise.",
            url_names=("journeys:learn",),
            feature="plain summaries per platform and guided exercises",
            section="4.8",
            hackathon="Refined focus: also for education applied purposes.",
        ),
    )
}


def roles_using(mockup: Mockup) -> list[Role]:
    """The journeys with a step that leads to ``mockup``."""
    return [role for role in ROLES if any(step.url_name in mockup.url_names for step in role.steps)]


def render_mockup(
    request: HttpRequest, key: str, template: str, context: dict[str, Any] | None = None
) -> HttpResponse:
    """A mock-up page in its frame (``journeys/prototype/base.html``): the banner, the title,
    and where the page fits."""
    mockup = MOCKUPS[key]
    frame = {"mockup": mockup, "mockup_roles": roles_using(mockup)}
    return render(request, template, frame | (context or {}))


def find_platform(slug: str) -> tuple[str, Platform | None]:
    """The platform's name and, if this database has it, the platform itself: a mock-up works
    for the demo platforms before ``seed_demo`` ran (and says so), and for any platform that
    exists. Any other slug is a 404."""
    platform = Platform.objects.filter(slug=slug).first()
    if platform is not None:
        return platform.name, platform
    if slug in DEMO_PLATFORMS:
        return DEMO_PLATFORMS[slug], None
    raise Http404
