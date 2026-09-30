"""The landing page (pick a role), a journey per role, and the feature cards. The mock-up pages
that journeys lead to are in ``mockups``."""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.journeys.content import ROLES, ROLES_BY_SLUG
from ddp_tracker.journeys.feature_cards import CARDS
from ddp_tracker.journeys.targets import demo_link
from ddp_tracker.schemas.models import Observation


def index(request: HttpRequest) -> HttpResponse:
    """What brings you here? The eight roles, how the tracker works, and what it holds today
    (only uploads that count: registered)."""
    points = Observation.objects.filter(is_data_point=True, upload__registered_at__isnull=False)
    counts = [
        ("Platforms", Platform.objects.count()),
        ("Uploads", Upload.objects.filter(registered_at__isnull=False).count()),
        ("Data points", points.values("location").distinct().count()),
        ("Annotations", Annotation.objects.count()),
    ]
    return render(request, "journeys/index.html", {"roles": ROLES, "counts": counts})


def journey(request: HttpRequest, role: str) -> HttpResponse:
    """One role's journey: its aim, its steps (each with its links) and the features it needs."""
    found = ROLES_BY_SLUG.get(role)
    if found is None:
        raise Http404
    context = {
        "role": found,
        "steps": [(step, demo_link(step.demo_link, request.user)) for step in found.steps],
        "others": [other for other in ROLES if other != found],
        # several steps link to TikTok's pages: they need the demo data (manage.py seed_demo)
        "has_demo_data": Upload.objects.filter(
            platform__slug="tiktok", registered_at__isnull=False
        ).exists(),
    }
    return render(request, "journeys/journey.html", context)


def features(request: HttpRequest) -> HttpResponse:
    """The planned features as feature cards, in the hackathon's template."""
    return render(request, "journeys/features.html", {"cards": CARDS})
