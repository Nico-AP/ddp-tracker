"""The collected schema of a platform (public explorer) and triaging its data points (the
explorer's panel and the review, ``reviews``, share it).

The explorer shows one root format's data points as a tree (``schemas/tree.py``,
``schemas/explorer.py``), like the review.
"""

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.ddps.values import own_values
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import ProposalError, submit
from ddp_tracker.schemas.explorer import (
    MISSING_ANNOTATIONS,
    MISSING_REPRESENTATIONS,
    SHOW,
    SHOW_ALL,
    explorer_tree,
)
from ddp_tracker.schemas.explorer import build_row as explorer_row_of
from ddp_tracker.schemas.filters import FilterForm, SchemaFilter, format_label, root_formats
from ddp_tracker.schemas.forms import ExamplesForm
from ddp_tracker.schemas.json_view import json_path
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.services import (
    choices,
    list_name,
)
from ddp_tracker.schemas.timeline import new_in
from ddp_tracker.schemas.tree import pending_counts
from ddp_tracker.users.auth import signed_in_user


def _explorer_context(request: HttpRequest, platform: Platform) -> dict[str, Any]:
    schema_filter = SchemaFilter.from_request(request, platform)
    q = request.GET.get("q", "").strip()
    show = request.GET.get("show", SHOW_ALL)
    show = show if show in SHOW else SHOW_ALL
    return {
        "platform": platform,
        "filter": schema_filter,
        "q": q,
        "show": show,
        "show_choices": [
            (SHOW_ALL, "Show all"),
            (MISSING_ANNOTATIONS, "Show missing annotations"),
            (MISSING_REPRESENTATIONS, "Show missing representations"),
        ],
        "tree": explorer_tree(platform, schema_filter, q, show=show),
        "row_template": "schemas/tree/_row.html",
    }


def platform_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """The collected schema of one root format, as a tree; with htmx (the filter box, the
    switch), only the tree's groups."""
    platform = get_object_or_404(Platform, slug=slug)
    context = _explorer_context(request, platform)
    if request.headers.get("HX-Request"):
        return render(request, "schemas/tree/_groups.html", context)
    schema_filter: SchemaFilter = context["filter"]
    observations = schema_filter.observations(platform)
    data_points = platform.locations.filter(
        observations__in=observations.filter(is_data_point=True)
    ).distinct()
    context |= {
        "filter_form": FilterForm(request.GET or None, platform=platform),
        "formats": [
            (value, format_label(value), count, schema_filter.with_format(value))
            for value, count in root_formats(platform)
        ],
        "counts": {
            "annotations": platform.annotations.count(),
            "data_points": data_points.count(),
            "untriaged": data_points.filter(annotation__isnull=True, ignored=False).count(),
            "uploads": schema_filter.uploads(platform).count(),
        },
        "uploads": platform.uploads.all()[:20] if request.user.is_authenticated else None,
    }
    return render(request, "schemas/platform_detail.html", context)


def explorer_row(request: HttpRequest, slug: str, location_pk: int) -> HttpResponse:
    """HTMX: one row of the explorer's tree, reloaded after a change."""
    platform = get_object_or_404(Platform, slug=slug)
    location = get_object_or_404(Location, pk=location_pk, platform=platform)
    schema_filter = SchemaFilter.from_request(request, platform)
    row = explorer_row_of(platform, schema_filter, location)[0]
    context = {"platform": platform, "filter": schema_filter, "row": row}
    return render(request, "schemas/tree/_row.html", context)


def location_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """HTMX: the explorer's side panel of a location: its annotation (for a list's row: the
    item's and the list's), examples, representations, structure and history."""
    platform = get_object_or_404(Platform, slug=slug)
    schema_filter = SchemaFilter.from_request(request, platform)
    location = get_object_or_404(
        Location.objects.select_related("annotation"),
        platform=platform,
        path=request.GET.get("path", ""),
    )
    observations = schema_filter.observations(platform)
    context = panel_context(location, observations, observations, schema_filter)
    locations = [location]
    if context["profile"].is_data_point:
        row = explorer_row_of(platform, schema_filter, location)[0]
        locations = [row.primary, *(loc for loc in row.locations if loc != row.primary)]
    # the item (the meaning) first
    context["entries"] = [(_annotation_label(loc, locations), loc) for loc in locations]
    context["decided"] = all(loc.annotation_id or loc.ignored for loc in locations)
    context["ignored"] = all(loc.ignored for loc in locations)
    context["triggers"] = ", ".join(f"triaged-{loc.pk} from:body" for loc in locations)
    context["suggestion_locations"] = locations
    context["pending"] = sum(pending_counts(loc.pk for loc in locations).values())
    return render(request, "schemas/_location_sidepanel.html", context)


def _annotation_label(location: Location, locations: list[Location]) -> str:
    if len(locations) == 1:
        return "Annotation"
    return "Each item" if location.path.endswith(ITEM) else "The list"


def panel_context(
    location: Location,
    observations: QuerySet[Observation],
    history_from: QuerySet[Observation],
    schema_filter: SchemaFilter,
    observation: Observation | None = None,
) -> dict[str, Any]:
    """The side panel of a location: its profile and JSON within ``observations``, its history
    within ``history_from``; ``observation`` is the upload being reviewed, if any."""
    history = (
        history_from.filter(location=location)
        .order_by("upload__requested_at")
        .values("upload__requested_at", "upload__language", "kind", "type", "shape", "format")
    )
    return {
        "platform": location.platform,
        "filter": schema_filter,
        "location": location,
        "profile": profiles([location.pk], observations)[location.pk],
        "json_path": json_path(location, observations),
        "history": history,
        "annotations": location.platform.annotations.all(),
        "observation": observation,
    }


@login_required
def location_examples(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: edit a location's example values; a valid POST returns the updated block."""
    location = get_object_or_404(Location, pk=pk)
    form = ExamplesForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        location = form.save()
        return render(request, "schemas/_examples.html", {"location": location})
    return render(request, "schemas/_examples_form.html", {"location": location, "form": form})


# --- triage (the explorer's panel and the review share it) -------------------------------


def _row_context(request: HttpRequest, location: Location) -> dict[str, Any]:
    """Context of a triage row and its modal. ``upload`` (query or form) is the upload being
    reviewed; it's absent when triaging from the explorer.
    """
    upload_id = request.POST.get("upload") or request.GET.get("upload") or None
    observation = (
        Observation.objects.filter(location=location, upload_id=upload_id)
        .select_related("location", "location__annotation", "upload")
        .first()
        if upload_id
        else None
    )
    found = choices(observation) if observation else []
    is_new = observation is not None and location.pk in new_in(observation.upload)
    upload = observation.upload if observation else None
    return {
        "location": location,
        "observation": observation,
        "upload": upload,
        "own": own_values(request, upload),
        "is_new": is_new,
        "choices": found,
        "annotations": location.platform.annotations.all(),
        **_list_context(location),
    }


def _list_context(location: Location) -> dict[str, Any]:
    """For a list whose item is annotated: the suggested name ("List of ID"). A list is
    annotated in its own step, after its item (which carries the meaning)."""
    item = (
        Location.objects.filter(
            platform=location.platform_id, path=location.path + ITEM, annotation__isnull=False
        )
        .select_related("annotation")
        .first()
    )
    return {"list_suggestion": list_name(item.annotation.name) if item and item.annotation else ""}


@login_required
def triage(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: decide what a data point is. GET: the modal with the choices. POST: apply one (staff)
    or suggest it (everyone else: ``proposals``); returns nothing (closing the modal) and
    triggers ``triaged-<pk>`` so the row reloads (and shows a suggestion as pending).
    """
    location = get_object_or_404(Location.objects.select_related("platform", "annotation"), pk=pk)
    if request.method != "POST":
        return render(request, "schemas/_triage_modal.html", _row_context(request, location))
    action = request.POST.get("action", "")
    targets: dict[str, Any] = {"location": location}
    if action == "link":
        targets["annotation"] = get_object_or_404(
            Annotation, pk=request.POST.get("annotation"), platform=location.platform
        )
    elif action == "new":
        targets["values"] = {
            field: request.POST.get(field, "").strip() for field in ("name", "description", "note")
        }
    kind = TRIAGE_KINDS.get(action)
    if kind is None:
        return HttpResponse(status=400)
    try:
        submit(signed_in_user(request), kind, comment=request.POST.get("comment", ""), **targets)
    except ProposalError as error:
        context = _row_context(request, location) | {"error": str(error)}
        return render(request, "schemas/_triage_modal.html", context)
    return HttpResponse(headers={"HX-Trigger": f"triaged-{location.pk}"})


TRIAGE_KINDS = {
    "link": Proposal.Kind.LINK,
    "new": Proposal.Kind.NEW_ANNOTATION,
    "ignore": Proposal.Kind.IGNORE,
    "reset": Proposal.Kind.UNASSIGN,
}
