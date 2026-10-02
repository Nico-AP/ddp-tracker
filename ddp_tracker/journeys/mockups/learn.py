"""M12, for learners: what a platform keeps about you, in plain words, and a short exercise.
The categories and the questions are written for this mock-up; how many data points each
category has is counted from the database.
"""

from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup
from ddp_tracker.schemas.models import Location


@dataclass(frozen=True)
class Category:
    name: str
    text: str
    prefixes: tuple[str, ...]  # the paths that belong to it

    @property
    def summary(self) -> str:
        """The text without the name it starts with (the name is the panel's heading)."""
        rest = self.text.removeprefix(f"{self.name}: ")
        return rest[:1].upper() + rest[1:]


T = "/user_data_tiktok.json"
_ACTIVITY = "What you did: what you watched, searched for, liked and commented on."
_MESSAGES = "Your messages: the private messages you sent and received, with their text."
_ADS = "Ads and other companies: what is known about you for advertising, and who told whom."
_DEVICES = "Devices and logins: when and from where you logged in, and with which device."
_PROFILE = "Your profile and connections: what you told the platform, and whom you follow."

CATEGORIES: dict[str, tuple[Category, ...]] = {
    "tiktok": (
        Category(
            "What you did",
            _ACTIVITY,
            (
                f"{T}/Your Activity/Watch History",
                f"{T}/Your Activity/Searches",
                f"{T}/Your Activity/Share History",
                f"{T}/Your Activity/Hashtag",
                f"{T}/Likes and Favorites",
                f"{T}/Comment",
                f"{T}/Post",
                f"{T}/Tiktok Live",
            ),
        ),
        Category("Your messages", _MESSAGES, (f"{T}/Direct Message",)),
        Category("Ads and other companies", _ADS, (f"{T}/Ads and data",)),
        Category(
            "Devices and logins",
            _DEVICES,
            (f"{T}/Your Activity/Login History", f"{T}/Your Activity/Most Recent Location Data"),
        ),
        Category("Your profile and connections", _PROFILE, (f"{T}/Profile And Settings",)),
    ),
    "instagram": (
        Category(
            "What you did",
            _ACTIVITY,
            (
                "/your_instagram_activity/likes",
                "/your_instagram_activity/saved",
                "/your_instagram_activity/comments",
                "/your_instagram_activity/story_interactions",
                "/your_instagram_activity/media",
                "/logged_information",
            ),
        ),
        Category("Your messages", _MESSAGES, ("/your_instagram_activity/messages",)),
        Category("Ads and other companies", _ADS, ("/ads_information",)),
        Category("Devices and logins", _DEVICES, ("/security_and_login_information",)),
        Category(
            "Your profile and connections",
            _PROFILE,
            ("/personal_information", "/connections"),
        ),
    ),
    "facebook": (
        Category(
            "What you did",
            _ACTIVITY,
            (
                "/your_facebook_activity/posts",
                "/your_facebook_activity/comments_and_reactions",
                "/your_facebook_activity/groups",
                "/your_facebook_activity/events",
                "/your_facebook_activity/pages",
                "/logged_information",
            ),
        ),
        Category("Your messages", _MESSAGES, ("/your_facebook_activity/messages",)),
        Category(
            "Ads and other companies",
            _ADS,
            ("/ads_information", "/apps_and_websites_off_of_facebook"),
        ),
        Category("Devices and logins", _DEVICES, ("/security_and_login_information",)),
        Category(
            "Your profile and connections",
            _PROFILE,
            ("/personal_information", "/connections"),
        ),
    ),
}

# the data point explained on the page: the annotation's name, per platform (demo/spec.py)
EXPLAINED: dict[str, str] = {
    "tiktok": "Watched video",
    "instagram": "Liked post",
    "facebook": "Reaction to a post",
}


@dataclass(frozen=True)
class Question:
    text: str
    answer: str


QUIZ: tuple[Question, ...] = (
    Question(
        "A package lists every video that was shown to you, with the date and time. Does "
        "that tell a researcher how long you watched each one?",
        "No. It says that a video was shown and when. How long you watched is not in this "
        "list; the gap until the next video is only a hint.",
    ),
    Question(
        "A timestamp reads 2026-09-01 08:15:42, without a time zone. Was that a quarter "
        "past eight in the morning where you were?",
        "Not necessarily. The value does not say whose clock it is. For this platform it "
        "looks like UTC, so in Amsterdam in summer it was a quarter past ten.",
    ),
    Question(
        "Your package contains the text of your private messages. Does the DDP Tracker "
        "keep those texts when you upload the package?",
        "No. The tracker reads the file, keeps only its structure (which fields exist and "
        "of what type) and deletes the file. The texts are never stored.",
    ),
)

# --- view ------------------------------------------------------------------------------------


def _count(platform: Platform, category: Category) -> int:
    """How many data points of uploads that count lie under the category's paths."""
    under = Q()
    for prefix in category.prefixes:
        under |= Q(path__startswith=prefix)
    return (
        platform.locations.filter(
            under,
            observations__is_data_point=True,
            observations__upload__registered_at__isnull=False,
        )
        .distinct()
        .count()
    )


def _explained(platform: Platform, name: str) -> dict[str, Any] | None:
    """One annotation with the example values below its location in use now: the one created
    last (for "Watched video", the September path)."""
    annotation = Annotation.objects.filter(platform=platform, name=name).first()
    if annotation is None:
        return None
    location = annotation.locations.order_by("-pk").first()
    if location is None:
        return None
    below = (
        Location.objects.filter(platform=platform, path__startswith=f"{location.path}/")
        .exclude(example_values=[])
        .order_by("position", "path")
    )
    return {
        "annotation": annotation,
        "location": location,
        "search": next(part for part in reversed(location.path.split("/")) if part != "[]"),
        "examples": [
            (entry.path.removeprefix(f"{location.path}/"), str(entry.example_values[0]["value"]))
            for entry in below
        ],
    }


def learn(request: HttpRequest, slug: str) -> HttpResponse:
    """M12: a plain summary of a platform's package, one example, and a short exercise."""
    name, platform = find_platform(slug)
    categories = [
        (category, _count(platform, category) if platform is not None else None)
        for category in CATEGORIES.get(slug, ())
    ]
    context = {
        "slug": slug,
        "platform_name": name,
        "platform": platform,
        "categories": categories,
        "explained": (
            _explained(platform, EXPLAINED[slug])
            if platform is not None and slug in EXPLAINED
            else None
        ),
        "quiz": QUIZ,
        "others": [(other, DEMO_PLATFORMS[other]) for other in CATEGORIES if other != slug],
    }
    return render_mockup(request, "learn", "journeys/prototype/learn.html", context)
