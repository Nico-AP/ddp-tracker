"""M10, seeding annotations: instead of writing every annotation by hand, start from what exists
and check it. Three sources, as the hackathon notes list them: the platform's own documentation
(kept as its own kind of annotation), paired uploads, and labels suggested by AI.

Everything here is fictional, the "official" texts included: they are written for this mock-up,
not taken from any platform's documentation.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup

DOCS, PAIRS, AI = "docs", "pairs", "ai"
SOURCES: tuple[tuple[str, str], ...] = (
    (DOCS, "Official documentation"),
    (PAIRS, "Paired uploads"),
    (AI, "AI suggestions"),
)

# --- official documentation against what uploads show (Facebook) ---------------------------

MATCHED, NOT_OBSERVED, NOT_DOCUMENTED = "matched", "not-observed", "not-documented"
MATCH_LABELS = {
    MATCHED: "Matched",
    NOT_OBSERVED: "Documented but not observed",
    NOT_DOCUMENTED: "Observed but not documented",
}
FB = "/your_facebook_activity"


@dataclass(frozen=True)
class DocEntry:
    status: str
    documented: str = ""  # the documentation's name for it
    text: str = ""  # what the documentation says
    path: str = ""  # the matching data point in the uploads

    @property
    def status_label(self) -> str:
        return MATCH_LABELS[self.status]


DOC_PLATFORM = "facebook"
DOC_SOURCE = (
    "Facebook's help pages on downloaded information (fictional text, retrieved 1 September 2026)"
)
DOC_ENTRIES: tuple[DocEntry, ...] = (
    DocEntry(
        MATCHED,
        "Comments",
        "Comments you have posted on your own posts, on other people's posts or in groups.",
        f"{FB}/comments_and_reactions/comments.json/comments_v2/[]",
    ),
    DocEntry(
        MATCHED,
        "Likes and reactions",
        "Posts, comments and pages you have liked or reacted to.",
        f"{FB}/comments_and_reactions/likes_and_reactions_1.json/[]",
    ),
    DocEntry(
        MATCHED,
        "Your search history",
        "Words, phrases and names you have searched for.",
        "/logged_information/search/your_search_history.json/searches_v2/[]",
    ),
    DocEntry(
        NOT_OBSERVED,
        "Voice recordings and transcriptions",
        "Recordings you made with voice features, and their transcriptions.",
    ),
    DocEntry(
        NOT_OBSERVED,
        "Payment history",
        "Payments you have made through the platform.",
    ),
    DocEntry(
        NOT_DOCUMENTED,
        path="/logged_information/other_logged_information/ads_interests.json/topics_v2",
    ),
    DocEntry(
        NOT_DOCUMENTED,
        path="/ads_information/other_categories_used_to_reach_you.json/bcts",
    ),
)

# --- a paired donation set: the same account, requested twice with one difference ------------


@dataclass(frozen=True)
class PairRow:
    left: str  # the path in the first upload
    right: str  # the path in the second upload
    evidence: str  # why they are taken to be the same
    annotation: str = ""  # the annotation the first one has, to carry across


PAIR_TITLE = (
    "TikTok, JSON: account language English (15 September 2026) and Dutch (16 September 2026)"
)
PAIR_DIFFERS_IN = "Account language"
T = "/user_data_tiktok.json"
PAIR_ROWS: tuple[PairRow, ...] = (
    PairRow(
        f"{T}/Your Activity/Watch History/VideoList",
        f"{T}/Jouw activiteit/Kijkgeschiedenis/VideoList",
        "Same position, 300 items in both, the same types",
        "Watched video",
    ),
    PairRow(
        f"{T}/Your Activity/Searches/SearchList",
        f"{T}/Jouw activiteit/Zoekopdrachten/SearchList",
        "Same position, 40 items in both, the same types",
        "Search",
    ),
    PairRow(
        f"{T}/Likes and Favorites/Like List/ItemFavoriteList",
        f"{T}/Likes en favorieten/Like-lijst/ItemFavoriteList",
        "Same position, 80 items in both, the same types",
        "Liked video",
    ),
    PairRow(
        f"{T}/Profile And Settings/Block List/BlockList",
        f"{T}/Profiel en instellingen/Blokkeerlijst/BlockList",
        "Same position; empty in both, so the match is weak",
    ),
)

# --- labels suggested by AI, each waiting for a person ------------------------------------------


@dataclass(frozen=True)
class AiSuggestion:
    path: str
    label: str
    why: str
    confidence: str  # in words, not a number that looks exact


AI_SUGGESTIONS: tuple[AiSuggestion, ...] = (
    AiSuggestion(
        f"{T}/Your Activity/Share History/ShareHistoryList/[]",
        "Shared content",
        "The list has a date, a link and a method such as whatsapp or copy link.",
        "High",
    ),
    AiSuggestion(
        f"{T}/Likes and Favorites/Favorite Sounds/FavoriteSoundList/[]",
        "Favourite sound",
        "A date and a link to a sound page.",
        "High",
    ),
    AiSuggestion(
        f"{T}/Profile And Settings/Follower/IsFastLane",
        "Follower list is shortened?",
        "A yes or no value next to the follower list; its meaning is a guess.",
        "Low",
    ),
)
AI_NOTE = (
    "A label suggested by AI is never shown to the public before a person has checked it. "
    "Whether that should stay so is an open question for the track."
)

# --- view (placeholder; task 4.5 replaces it) -----------------------------------------------


def seed_sources(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "seed", "journeys/prototype/placeholder.html")
