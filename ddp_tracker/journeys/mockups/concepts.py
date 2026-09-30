"""M1 and M2, the concept view: what people do on platforms, as concepts that mean the same
everywhere. It is the researcher's view, next to the explorer's structure view.

The concepts, the research fields and their themes are fictional: a field-specific ontology does
not exist yet. What is real comes from the database: a concept is bound, per platform, to an
annotation that ``seed_demo`` creates (``demo/spec.py``), and its paths, types, dates and
examples are read from there.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Upload
from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, render_mockup
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles


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


# --- what the database knows about a concept ------------------------------------------------


@dataclass
class FieldView:
    """One data point: a field of a list's item, or a value on its own."""

    location: Location
    profile: Profile

    @property
    def name(self) -> str:
        return self.location.display_name

    @property
    def example(self) -> str:
        examples = self.location.example_values
        return str(examples[0]["value"]) if examples else ""


@dataclass
class LocationView:
    """An annotated location, with what the uploads that count say about it."""

    location: Location
    profile: Profile
    languages: list[str]
    fields: list[FieldView]  # a list's item: its direct fields; a single value: itself
    examples: list[tuple[str, str]]  # (title, value) rows for the examples table


@dataclass
class PlatformView:
    """A concept on one platform: the annotation that describes it there, if this database has
    it (``seed_demo``), and its locations, the path in use now first."""

    binding: Binding
    name: str
    annotation: Annotation | None
    locations: list[LocationView]


@dataclass(frozen=True)
class Availability:
    """A concept at a glance, over all its platforms."""

    known: bool  # this database has at least one of the annotations
    first_seen: date | None
    last_seen: date | None
    uploads: int  # uploads that count and contain it, all platforms
    pii: bool


def _counted() -> QuerySet[Observation]:
    """Only uploads that count: registered."""
    return Observation.objects.filter(upload__registered_at__isnull=False)


def _examples(location: Location) -> list[tuple[str, str]]:
    """Example values as rows of title and value: for a list's item, the data points below it
    that have examples (by their path below the item); for a single value, its own."""
    if not location.path.endswith(ITEM):
        return [
            (location.display_name, str(example["value"])) for example in location.example_values
        ]
    below = (
        Location.objects.filter(platform=location.platform_id, path__startswith=f"{location.path}/")
        .exclude(example_values=[])
        .order_by("position", "path")
    )
    return [
        (entry.path.removeprefix(f"{location.path}/"), str(entry.example_values[0]["value"]))
        for entry in below
    ]


def _location_view(location: Location) -> LocationView:
    children: list[Location] = []
    if location.path.endswith(ITEM):  # a list's item: its direct fields
        children = list(
            Location.objects.filter(platform=location.platform_id, parent_path=location.path)
            .exclude(name=None)
            .order_by("position")
        )
    found = profiles([location.pk, *(child.pk for child in children)], _counted())
    fields = [FieldView(child, found[child.pk]) for child in children]
    seen = location.observations.filter(upload__registered_at__isnull=False)
    languages = sorted(
        {code or "unknown" for code in seen.values_list("upload__language", flat=True)}
    )
    return LocationView(
        location=location,
        profile=found[location.pk],
        languages=languages,
        fields=fields or [FieldView(location, found[location.pk])],
        examples=_examples(location),
    )


def _last_seen(entry: LocationView) -> date:
    return entry.profile.last_seen or date.min


def resolve(concept: Concept) -> list[PlatformView]:
    """The concept on each platform it is bound to, with what this database knows about it."""
    views = []
    for binding in concept.bindings:
        annotation = (
            Annotation.objects.filter(platform__slug=binding.platform, name=binding.annotation)
            .select_related("platform")
            .first()
        )
        if annotation is None:  # no demo data: the binding alone
            views.append(PlatformView(binding, DEMO_PLATFORMS[binding.platform], None, []))
            continue
        locations = [_location_view(location) for location in annotation.locations.all()]
        locations.sort(key=_last_seen, reverse=True)
        views.append(PlatformView(binding, annotation.platform.name, annotation, locations))
    return views


def availability(views: list[PlatformView]) -> Availability:
    """A concept at a glance, over all its platforms."""
    entries = [entry for view in views for entry in view.locations]
    firsts = [entry.profile.first_seen for entry in entries if entry.profile.first_seen]
    lasts = [entry.profile.last_seen for entry in entries if entry.profile.last_seen]
    uploads = Upload.objects.filter(
        registered_at__isnull=False,
        observations__location__in=[entry.location.pk for entry in entries],
    )
    return Availability(
        known=any(view.annotation is not None for view in views),
        first_seen=min(firsts, default=None),
        last_seen=max(lasts, default=None),
        uploads=uploads.distinct().count(),
        pii=any(view.annotation.pii for view in views if view.annotation is not None),
    )


# --- views (task 3.2 replaces the placeholder concept_detail) -------------------------------


def _by_name(concept: Concept) -> str:
    return concept.name


def _by_relevance(concept: Concept) -> int:
    return -concept.studies


def concept_list(request: HttpRequest) -> HttpResponse:
    """M1: the concepts, narrowed by a research field's theme and by platform, sorted by
    relevance (how many studies use them: fictional) or by name."""
    chosen_field = FIELDS_BY_SLUG.get(request.GET.get("field", ""), FIELDS[0])
    themes = {theme.slug: theme for theme in chosen_field.themes}
    theme = themes.get(request.GET.get("theme", ""))  # a theme of another field: ignored
    platform = request.GET.get("platform", "")
    platforms = {
        slug: name
        for slug, name in DEMO_PLATFORMS.items()
        if any(slug in concept.platforms for concept in CONCEPTS)
    }
    if platform not in platforms:
        platform = ""
    sort = "name" if request.GET.get("sort") == "name" else "relevance"
    chosen = [
        concept
        for concept in CONCEPTS
        if (theme is None or theme.slug in concept.themes)
        and (not platform or platform in concept.platforms)
    ]
    chosen.sort(key=_by_name if sort == "name" else _by_relevance)
    cards: list[dict[str, Any]] = []
    for concept in chosen:
        views = resolve(concept)
        cards.append(
            {
                "concept": concept,
                "availability": availability(views),
                # every platform that has concepts, with whether this concept is there
                "platforms": [
                    (name, slug in concept.platforms) for slug, name in platforms.items()
                ],
                "themes": [t for t in chosen_field.themes if t.slug in concept.themes],
            }
        )
    context = {
        "fields": FIELDS,
        "field": chosen_field,
        "theme": theme,
        "platforms": platforms,
        "platform": platform,
        "sort": sort,
        "cards": cards,
        "has_data": any(card["availability"].known for card in cards),
    }
    return render_mockup(request, "concepts", "journeys/prototype/concepts.html", context)


def concept_detail(request: HttpRequest, slug: str) -> HttpResponse:
    return render_mockup(request, "concept", "journeys/prototype/placeholder.html")
