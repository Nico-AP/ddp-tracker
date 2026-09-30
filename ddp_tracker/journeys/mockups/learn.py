"""M12, for learners: what a platform keeps about you, in plain words, and a short exercise.
The categories and the questions are written for this mock-up; how many data points each
category has is counted from the database.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import find_platform, render_mockup


@dataclass(frozen=True)
class Category:
    name: str
    text: str
    prefixes: tuple[str, ...]  # the paths that belong to it


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

# --- view (placeholder; task 4.7 replaces it) -----------------------------------------------


def learn(request: HttpRequest, slug: str) -> HttpResponse:
    name, platform = find_platform(slug)
    context = {"platform_name": name, "platform": platform}
    return render_mockup(request, "learn", "journeys/prototype/placeholder.html", context)
