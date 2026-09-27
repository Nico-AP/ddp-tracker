"""The collected schema of a platform (public explorer) and the review of an upload (triage).

The explorer loads one level of the tree at a time (HTMX), so large schemas stay fast.
"""

from collections import Counter
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.schemas.filters import FilterForm, SchemaFilter, format_label
from ddp_tracker.schemas.forms import ExamplesForm
from ddp_tracker.schemas.json_view import json_path
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.services import (
    TriageItem,
    choices,
    create_annotation,
    create_with_list,
    ignore,
    link,
    list_name,
    review,
)
from ddp_tracker.schemas.timeline import new_in
from ddp_tracker.users.auth import signed_in_user


def _children(
    platform: Platform, parent_path: str, schema_filter: SchemaFilter
) -> list[dict[str, Any]]:
    """The locations below ``parent_path`` seen in the filtered uploads, each with its profile
    and how many children it has itself (in the same uploads).
    """
    observations = schema_filter.observations(platform)
    locations = list(
        platform.locations.filter(parent_path=parent_path, observations__in=observations)
        .distinct()
        .select_related("annotation")
    )
    counts = dict(
        platform.locations.filter(
            parent_path__in=[location.path for location in locations],
            observations__in=observations,
        )
        .values("parent_path")
        .annotate(count=Count("id", distinct=True))
        .values_list("parent_path", "count")
    )
    found = profiles((location.pk for location in locations), observations)
    # Files and folders sort by name, as within any single upload. Keys of parsed data keep
    # their order in the file; positions from different uploads can tie, so the path decides.
    locations.sort(
        key=lambda loc: (
            (loc.position, loc.path) if found[loc.pk].main_kind == "data" else (0, loc.name or "")
        )
    )
    return [
        {"location": loc, "profile": found[loc.pk], "children": counts.get(loc.path, 0)}
        for loc in locations
    ]


def root_formats(uploads: QuerySet[Upload]) -> list[tuple[str, int]]:
    """What the uploads were as a whole ("ZIP archive", "CSV file" …), most common first."""
    formats = Counter(
        format_label(value) for value in uploads.values_list("root_format", flat=True)
    )
    return formats.most_common()


def platform_detail(request: HttpRequest, slug: str) -> HttpResponse:
    platform = get_object_or_404(Platform, slug=slug)
    schema_filter = SchemaFilter.from_request(request, platform)
    observations = schema_filter.observations(platform)
    data_points = platform.locations.filter(
        observations__in=observations.filter(is_data_point=True)
    ).distinct()
    context = {
        "platform": platform,
        "filter": schema_filter,
        "filter_form": FilterForm(request.GET or None, platform=platform),
        "root": platform.locations.filter(path="", observations__in=observations).first(),
        "root_formats": root_formats(schema_filter.uploads(platform)),
        "rows": _children(platform, "", schema_filter),
        "counts": {
            "annotations": platform.annotations.count(),
            "data_points": data_points.count(),
            "untriaged": data_points.filter(annotation__isnull=True, ignored=False).count(),
            "uploads": schema_filter.uploads(platform).count(),
        },
        "uploads": platform.uploads.all()[:20] if request.user.is_authenticated else None,
    }
    return render(request, "schemas/platform_detail.html", context)


def location_children(request: HttpRequest, slug: str) -> HttpResponse:
    platform = get_object_or_404(Platform, slug=slug)
    schema_filter = SchemaFilter.from_request(request, platform)
    rows = _children(platform, request.GET.get("path", ""), schema_filter)
    context = {"platform": platform, "filter": schema_filter, "rows": rows}
    return render(request, "schemas/_tree.html", context)


def location_detail(request: HttpRequest, slug: str) -> HttpResponse:
    platform = get_object_or_404(Platform, slug=slug)
    schema_filter = SchemaFilter.from_request(request, platform)
    location = get_object_or_404(
        Location.objects.select_related("annotation"),
        platform=platform,
        path=request.GET.get("path", ""),
    )
    observations = schema_filter.observations(platform)
    context = _panel_context(location, observations, observations, schema_filter)
    return render(request, "schemas/_location_sidepanel.html", context)


def _panel_context(
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


# --- review and triage ------------------------------------------------------------------------


@login_required
def upload_review(request: HttpRequest, pk: int) -> HttpResponse:
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    tab = request.GET.get("tab", "assign")
    context = {
        "upload": upload,
        "review": review(upload) if upload.registered_at else None,
        "tab": tab if tab in {"assign", "changed", "missing"} else "assign",
    }
    return render(request, "schemas/review/base.html", context)


@login_required
def review_location(request: HttpRequest, pk: int, location_pk: int) -> HttpResponse:
    """HTMX: the side panel of a data point, as it is in the reviewed upload (a missing one: as
    in all uploads)."""
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    location = get_object_or_404(
        Location.objects.select_related("annotation", "platform"),
        pk=location_pk,
        platform=upload.platform,
    )
    counted = Observation.objects.filter(upload__registered_at__isnull=False)
    observation = upload.observations.filter(location=location).first()
    scope = upload.observations.all() if observation else counted
    context = _panel_context(location, scope, counted, SchemaFilter(), observation)
    return render(request, "schemas/_location_sidepanel.html", context)


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
    return {
        "location": location,
        "observation": observation,
        "item": TriageItem(observation, found, is_new) if observation else None,
        "upload": observation.upload if observation else None,
        "is_new": is_new,
        "choices": found,
        "annotations": location.platform.annotations.all(),
        "panel": bool(request.GET.get("panel")),  # the explorer's side panel
        **_list_context(location),
    }


def _list_context(location: Location) -> dict[str, Any]:
    """For a list's item: whether its list could get the suggested annotation too. For a list
    whose item is annotated: the suggested name ("List of ID").
    """
    platform = location.platform_id
    if location.path.endswith(ITEM):
        parent = Location.objects.filter(platform=platform, path=location.parent_path).first()
        free = parent is not None and parent.annotation_id is None and not parent.ignored
        return {"list_open": free}
    item = (
        Location.objects.filter(
            platform=platform, path=location.path + ITEM, annotation__isnull=False
        )
        .select_related("annotation")
        .first()
    )
    return {"list_suggestion": list_name(item.annotation.name) if item and item.annotation else ""}


def triage_row(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: a data point's triage row (read-only, reloaded after a change)."""
    location = get_object_or_404(Location.objects.select_related("platform", "annotation"), pk=pk)
    context = _row_context(request, location)
    # a review row needs the reviewed upload; everything else is the side panel's block
    in_review = context["item"] is not None and not context["panel"]
    template = "schemas/review/_review_row.html" if in_review else "schemas/_triage_panel.html"
    return render(request, template, context)


@login_required
def triage(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: decide what a data point is. GET: the modal with the choices. POST: apply one;
    returns nothing (closing the modal) and triggers ``triaged-<pk>`` so the row reloads.
    """
    location = get_object_or_404(Location.objects.select_related("platform", "annotation"), pk=pk)
    if request.method != "POST":
        return render(request, "schemas/_triage_modal.html", _row_context(request, location))
    action = request.POST.get("action")
    if action == "link":
        annotation = get_object_or_404(
            Annotation, pk=request.POST.get("annotation"), platform=location.platform
        )
        link(location, annotation)
    elif action == "new":
        name, user = request.POST.get("name", ""), signed_in_user(request)
        if request.POST.get("with_list"):
            create_with_list(location, name, user)
        else:
            create_annotation(location, name, user)
    elif action == "ignore":
        ignore(location)
    elif action == "reset":
        link(location, None)
    return HttpResponse(headers={"HX-Trigger": f"triaged-{location.pk}"})
