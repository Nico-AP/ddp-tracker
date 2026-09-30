"""M9, the moderator's dashboard: what waits on the platforms someone moderates. The assignment
of platforms, the community's questions and the contributors are fictional; the queues are
counted from the database.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup

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

# --- view (placeholder; task 4.4 replaces it) -----------------------------------------------


def dashboard(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "moderate", "journeys/prototype/placeholder.html")
