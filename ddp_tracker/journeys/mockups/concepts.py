"""M1 and M2, the concept view: what people do on platforms, as concepts that mean the same
everywhere. It is the researcher's view, next to the explorer's structure view.

The concepts, the research fields and their themes are fictional: a field-specific ontology does
not exist yet. What is real comes from the database: a concept is bound, per platform, to an
annotation that ``seed_demo`` creates (``demo/spec.py``), and its paths, types, dates and
examples are read from there.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup


@dataclass(frozen=True)
class Theme:
    slug: str
    name: str


@dataclass(frozen=True)
class Field:
    """A research field with its own themes: a field-specific ontology on top of the concepts."""

    slug: str
    name: str
    themes: tuple[Theme, ...]


FIELDS: tuple[Field, ...] = (
    Field(
        "communication",
        "Communication science",
        (
            Theme("news-politics", "News and politics"),
            Theme("entertainment", "Entertainment"),
            Theme("social-ties", "Social ties"),
            Theme("advertising", "Advertising"),
        ),
    ),
    Field(
        "health",
        "Public health",
        (
            Theme("wellbeing", "Wellbeing and screen time"),
            Theme("health-information", "Health information seeking"),
            Theme("social-support", "Social support"),
            Theme("commercial-exposure", "Commercial exposure"),
        ),
    ),
    Field(
        "economics",
        "Economics",
        (
            Theme("consumer-behaviour", "Consumer behaviour"),
            Theme("ad-exposure", "Advertising exposure"),
            Theme("attention", "Attention and time use"),
        ),
    ),
)
FIELDS_BY_SLUG = {field.slug: field for field in FIELDS}

# Whose time a timestamp shows: the attribute the hackathon proposes (tz_whos).
UTC_ASSUMED = "UTC (assumed: the values carry no time zone marker)"
UNIX_TIME = "UTC (a Unix timestamp counts the seconds since 1970 in UTC)"

# How settled a concept's meaning is.
AGREED, DISCUSSED = "agreed", "discussed"
MEANINGS = {AGREED: "Agreed by curators", DISCUSSED: "Under discussion"}


@dataclass(frozen=True)
class Binding:
    """Where a platform provides a concept: the annotation that describes it there."""

    platform: str  # slug
    annotation: str  # the name of the annotation seed_demo creates
    tz_whos: str
    official: str = ""  # what the platform's documentation says (fictional text)
    no_data: tuple[str, ...] = ()  # values that mean "no data"


@dataclass(frozen=True)
class Concept:
    slug: str
    name: str
    description: str
    statement: str  # in the shared vocabulary: actor, activity, object
    themes: tuple[str, ...]  # theme slugs, across the fields
    studies: int  # fictional: how many studies have it on their shortlist
    meaning: str
    bindings: tuple[Binding, ...]
    translations: tuple[tuple[str, str], ...] = ()  # (language, the concept's name)

    @property
    def meaning_label(self) -> str:
        return MEANINGS[self.meaning]

    @property
    def platforms(self) -> tuple[str, ...]:
        return tuple(binding.platform for binding in self.bindings)


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        slug="watched-video",
        name="Watched a video",
        description="A video was shown to the user, with when. How long they watched is not said.",
        statement="user · viewed · video",
        themes=("news-politics", "entertainment", "wellbeing", "attention"),
        studies=14,
        meaning=AGREED,
        bindings=(
            Binding(
                "tiktok",
                "Watched video",
                UTC_ASSUMED,
                official="Watch History: the videos you watched, with the date and time.",
            ),
            Binding("instagram", "Video watched", UNIX_TIME),
            Binding(
                "facebook",
                "Video watched",
                UNIX_TIME,
                official="Recently viewed: videos and other items you have viewed recently.",
            ),
        ),
        translations=(("Dutch", "Video bekeken"), ("German", "Video angesehen")),
    ),
    Concept(
        slug="searched",
        name="Searched",
        description="The user typed something into the platform's search, with when.",
        statement="user · searched · object",
        themes=("news-politics", "health-information", "consumer-behaviour"),
        studies=11,
        meaning=AGREED,
        bindings=(
            Binding("tiktok", "Search", UTC_ASSUMED),
            Binding("instagram", "Keyword search", UNIX_TIME),
            Binding(
                "facebook",
                "Search",
                UNIX_TIME,
                official="Your search history: words, phrases and names you have searched for.",
            ),
        ),
        translations=(("Dutch", "Gezocht"), ("German", "Gesucht")),
    ),
    Concept(
        slug="liked-content",
        name="Liked or reacted to content",
        description="The user liked a post or a video, or reacted to it in another way.",
        statement="user · responded · video, image or note",
        themes=("entertainment", "social-ties", "wellbeing", "attention"),
        studies=9,
        meaning=DISCUSSED,
        bindings=(
            Binding("tiktok", "Liked video", UTC_ASSUMED),
            Binding("instagram", "Liked post", UNIX_TIME),
            Binding(
                "facebook",
                "Reaction to a post",
                UNIX_TIME,
                official="Likes and reactions: posts, comments and pages you have reacted to.",
            ),
        ),
        translations=(("Dutch", "Geliked of gereageerd"), ("German", "Geliked oder reagiert")),
    ),
    Concept(
        slug="commented",
        name="Wrote a comment",
        description="The user wrote a comment under a post or a video, with when.",
        statement="user · created · note",
        themes=("news-politics", "social-ties", "social-support"),
        studies=7,
        meaning=AGREED,
        bindings=(
            Binding("tiktok", "Comment written", UTC_ASSUMED, no_data=("N/A",)),
            Binding("instagram", "Comment written", UNIX_TIME),
            Binding("facebook", "Comment written", UNIX_TIME),
        ),
    ),
    Concept(
        slug="followed-account",
        name="Followed an account",
        description="The user follows another account, a page or a channel, with since when.",
        statement="user · followed · profile",
        themes=("news-politics", "social-ties", "consumer-behaviour"),
        studies=6,
        meaning=AGREED,
        bindings=(
            Binding("tiktok", "Account followed", UTC_ASSUMED),
            Binding("instagram", "Account followed", UNIX_TIME),
            Binding("facebook", "Account followed", UNIX_TIME),
        ),
    ),
    Concept(
        slug="saw-ad",
        name="Saw an ad",
        description="An ad was shown to the user, with when and the advertiser.",
        statement="user · viewed · note",
        themes=("advertising", "commercial-exposure", "ad-exposure"),
        studies=5,
        meaning=DISCUSSED,
        bindings=(Binding("instagram", "Ad viewed", UNIX_TIME),),
    ),
    Concept(
        slug="off-platform-activity",
        name="Activity reported by other companies",
        description=(
            "Something the user did in another company's shop, app or website, which that "
            "company reported to the platform."
        ),
        statement="platform · added · event",
        themes=("advertising", "commercial-exposure", "consumer-behaviour", "ad-exposure"),
        studies=4,
        meaning=DISCUSSED,
        bindings=(
            Binding("tiktok", "Off-platform activity event", UTC_ASSUMED),
            Binding(
                "facebook",
                "Off-Meta activity event",
                UNIX_TIME,
                official=(
                    "Your activity off Meta technologies: information that businesses and "
                    "organisations share with us about your interactions with them."
                ),
            ),
        ),
    ),
    Concept(
        slug="sent-message",
        name="Sent or received a direct message",
        description="The text of a private message between the user and someone else.",
        statement="user · created · note",
        themes=("social-ties", "social-support"),
        studies=3,
        meaning=AGREED,
        bindings=(
            Binding("tiktok", "Direct message text", UTC_ASSUMED),
            Binding("instagram", "Direct message text", UNIX_TIME),
            Binding("facebook", "Direct message text", UNIX_TIME),
        ),
    ),
    Concept(
        slug="logged-in",
        name="Logged in",
        description="The user logged in to the account, with the device and the IP address.",
        statement="user · opened · object",
        themes=("wellbeing", "attention"),
        studies=2,
        meaning=AGREED,
        bindings=(
            Binding("tiktok", "Login", UTC_ASSUMED),
            Binding("instagram", "Login", UNIX_TIME),
            Binding("facebook", "Login or logout", UNIX_TIME),
        ),
    ),
)
CONCEPTS_BY_SLUG = {concept.slug: concept for concept in CONCEPTS}


# --- views (placeholders; task 3.1 replaces concept_list, task 3.2 concept_detail) ----------


def concept_list(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "concepts", "journeys/prototype/placeholder.html")


def concept_detail(request: HttpRequest, slug: str) -> HttpResponse:
    return render_mockup(request, "concept", "journeys/prototype/placeholder.html")
