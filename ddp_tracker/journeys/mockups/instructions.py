"""M8, how to request a data download package from a platform. The steps are written to be
plausible, not checked: the page marks them "to be verified by curators", with a made-up date.
"""

from dataclasses import dataclass
from datetime import date

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup


@dataclass(frozen=True)
class Instructions:
    steps: tuple[str, ...]
    choose: str  # which options to choose, so that the tracker can read the package
    wait: str  # how long it takes
    receive: str  # what arrives
    last_checked: date  # fictional


PAIR_HINT = (
    "Want to help more? Request the same package twice, with one thing different: another "
    "account language, or HTML next to JSON. Such a pair shows curators which fields are the "
    "same under different names."
)

INSTRUCTIONS: dict[str, Instructions] = {
    "tiktok": Instructions(
        steps=(
            "Open TikTok and go to your profile.",
            "Open the menu and choose Settings and privacy.",
            "Choose Account, then Download your data.",
            "Select what to include (all data, or only some) and the file format.",
            "Choose Request data.",
            "Come back to the tab Download data when the package is ready, and download it.",
        ),
        choose="File format: JSON (not TXT).",
        wait="From a few minutes to a few days.",
        receive="A zip file with one file in it: user_data_tiktok.json.",
        last_checked=date(2026, 9, 1),
    ),
    "instagram": Instructions(
        steps=(
            "Open Instagram and go to your profile.",
            "Open the menu and choose Accounts Centre.",
            "Choose Your information and permissions, then Download your information.",
            "Choose Download or transfer information, and select your Instagram account.",
            "Choose which information, then Download to device.",
            "Set the date range and the format, and choose Create files.",
            "You get a message when the files are ready: download them from the same page.",
        ),
        choose="Format: JSON (not HTML). Date range: All time. Media quality: Low is enough.",
        wait="Up to 48 hours.",
        receive="One or more zip files with folders such as your_instagram_activity.",
        last_checked=date(2026, 9, 1),
    ),
    "facebook": Instructions(
        steps=(
            "Open Facebook and go to Settings and privacy, then Settings.",
            "Choose Accounts Centre.",
            "Choose Your information and permissions, then Download your information.",
            "Choose Download or transfer information, and select your Facebook profile.",
            "Choose which information, then Download to device.",
            "Set the date range and the format, and choose Create files.",
            "You get a message when the files are ready: download them from the same page.",
        ),
        choose="Format: JSON (not HTML). Date range: All time. Media quality: Low is enough.",
        wait="Up to 48 hours.",
        receive="One or more zip files with folders such as your_facebook_activity.",
        last_checked=date(2026, 9, 1),
    ),
    "youtube": Instructions(
        steps=(
            "Go to Google Takeout (takeout.google.com) and sign in.",
            "Choose Deselect all, then select YouTube and YouTube Music.",
            "Choose Multiple formats and set History to JSON.",
            "Choose Next step, then Create export.",
            "You get an e-mail when the export is ready: download it from the link.",
        ),
        choose="History: JSON (the default is HTML). File type: zip.",
        wait="From minutes to a few hours.",
        receive="A zip file with a folder Takeout, and in it YouTube and YouTube Music.",
        last_checked=date(2026, 8, 15),
    ),
}

# --- view ------------------------------------------------------------------------------------


def request_instructions(request: HttpRequest, slug: str) -> HttpResponse:
    """M8: how to request a data download package from one platform."""
    name, platform = find_platform(slug)
    context = {
        "slug": slug,
        "platform_name": name,
        "platform": platform,
        "instructions": INSTRUCTIONS.get(slug),
        "pair_hint": PAIR_HINT,
        "others": DEMO_PLATFORMS,
    }
    return render_mockup(request, "request", "journeys/prototype/request.html", context)
