"""M11, roles and platforms: who may do what, and on which platform, managed in the app instead
of the Django admin. The people, the hubs and the working groups are fictional; the platforms and
the path rules are read from the database.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    may: str
    today: str  # the closest thing that exists today


ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        "Administrator",
        "Add platforms and path rules, approve vocabulary terms, give and take roles.",
        "Staff with access to the Django admin",
    ),
    RoleDefinition(
        "Moderator",
        "On their platforms: approve uploads, decide on suggestions, appoint curators.",
        "Staff (for every platform at once)",
    ),
    RoleDefinition(
        "Curator",
        "On their platforms: annotate and describe representations directly.",
        "Staff (for every platform at once)",
    ),
    RoleDefinition(
        "Contributor",
        "Upload, suggest annotations and representations, add example values.",
        "Any signed-in user",
    ),
)


@dataclass(frozen=True)
class Person:
    account: str  # accounts show as numbers, never as e-mail addresses
    role: str
    platforms: tuple[str, ...] = ()  # names; empty means every platform, or none needed


PEOPLE: tuple[Person, ...] = (
    Person("#1", "Administrator"),
    Person("#7", "Moderator", ("TikTok", "Instagram")),
    Person("#12", "Moderator", ("Facebook",)),
    Person("#31", "Curator", ("TikTok",)),
    Person("#44", "Curator", ("YouTube",)),
    Person("#58", "Contributor"),
)


@dataclass(frozen=True)
class Hub:
    platform: str
    hub: str
    working_group: str


HUBS: tuple[Hub, ...] = (
    Hub("TikTok", "Example University A (fictional)", "Short video working group"),
    Hub("Instagram", "Example University A (fictional)", "Meta platforms working group"),
    Hub("Facebook", "Example Institute B (fictional)", "Meta platforms working group"),
    Hub("YouTube", "Example University C (fictional)", "Video platforms working group"),
)

# the rule from the parser's documentation, shown when the database has no rule of its own
EXAMPLE_RULE = (
    "/user_data_tiktok.json/Direct Message/Direct Messages/ChatHistory/Chat History with *"
)
EXAMPLE_RULE_NOTE = (
    "Renames the key of each chat, which contains the other person's username, to {*}."
)

# --- view (placeholder; task 4.6 replaces it) -----------------------------------------------


def roles(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "roles", "journeys/prototype/placeholder.html")
