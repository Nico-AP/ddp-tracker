"""M9, the moderator's dashboard: what waits on the platforms someone moderates. The assignment
of platforms, the community's questions and the contributors are fictional; the queues are
counted from the database.
"""

from dataclasses import dataclass
from typing import Any

from django.db.models import Count
from django.http import HttpRequest, HttpResponse

from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.representations.eligibility import eligible
from ddp_tracker.schemas.models import ITEM

# the platforms "you" moderate (a role for one or more platforms does not exist yet)
ASSIGNED: tuple[str, ...] = ("tiktok", "instagram")

HUB_NOTE = (
    "Each platform has a hub: a group that looks after it and appoints its moderators. "
    "The TikTok hub and the Instagram hub in this mock-up are made up."
)


@dataclass(frozen=True)
class Question:
    """A question curators ask everyone: crowdsourcing what one person cannot know."""

    platform: str
    path: str
    text: str
    answers: int


QUESTIONS: tuple[Question, ...] = (
    Question(
        "tiktok",
        "/user_data_tiktok.json/Profile And Settings/Follower/IsFastLane",
        "What does IsFastLane say about a follower list? Has anyone seen it set to true?",
        2,
    ),
    Question(
        "tiktok",
        "/user_data_tiktok.json/Ads and data/Off TikTok Activity/OffTikTokActivityDataList/[]/Event",
        "Which values does Event take in your package? We know Page View and Add to Cart.",
        5,
    ),
    Question(
        "instagram",
        "/ads_information/ads_and_topics/videos_watched.json/[]",
        "Is this list every video you watched, or only videos shown as ads?",
        1,
    ),
)


@dataclass(frozen=True)
class Contributor:
    account: str  # accounts show as numbers, never as e-mail addresses
    annotations: int
    uploads: int


CONTRIBUTORS: tuple[Contributor, ...] = (
    Contributor("#12", annotations=41, uploads=2),
    Contributor("#7", annotations=28, uploads=1),
    Contributor("#31", annotations=9, uploads=4),
)

# --- view -------------------------------------------------------------------------------------


def _queues(platform: Platform) -> dict[str, Any]:
    """What waits on a platform, counted as the explorer and the queues count it."""
    points = platform.locations.filter(
        observations__is_data_point=True, observations__upload__registered_at__isnull=False
    ).distinct()
    open_points = points.filter(annotation__isnull=True, ignored=False)
    lists = platform.locations.filter(path__endswith=ITEM, representations__isnull=True)
    return {
        "data_points": points.count(),
        "untriaged": open_points.count(),
        "suggestions": Proposal.objects.filter(
            platform=platform, status=Proposal.Status.OPEN
        ).count(),
        "approvals": platform.uploads.filter(plausibility=Upload.Plausibility.AWAITING).count(),
        "unrepresented": len(eligible(lists)),
        # the open data points that the most uploads have: annotate these first
        "next": list(
            open_points.annotate(seen=Count("observations__upload", distinct=True)).order_by(
                "-seen", "path"
            )[:5]
        ),
    }


def dashboard(request: HttpRequest) -> HttpResponse:
    """M9: what waits on the platforms a moderator looks after."""
    panels = []
    for slug in ASSIGNED:
        name, platform = find_platform(slug)
        panels.append(
            {
                "slug": slug,
                "name": name,
                "platform": platform,
                "queues": _queues(platform) if platform is not None else None,
            }
        )
    elsewhere = (
        Upload.objects.filter(plausibility=Upload.Plausibility.AWAITING)
        .exclude(platform__slug__in=ASSIGNED)
        .count()
    )
    context = {
        "panels": panels,
        "elsewhere": elsewhere,
        "hub_note": HUB_NOTE,
        # each question with its platform's name
        "questions": [(DEMO_PLATFORMS[question.platform], question) for question in QUESTIONS],
        "contributors": CONTRIBUTORS,
        "has_data": any(panel["platform"] is not None for panel in panels),
    }
    return render_mockup(request, "moderate", "journeys/prototype/moderate.html", context)
