"""The collected schema of a platform (public explorer) and the review of an upload (triage).

The explorer loads one level of the tree at a time (HTMX), so large schemas stay fast.
"""

from collections import Counter
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.schemas.filters import FilterForm, SchemaFilter, format_label
from ddp_tracker.schemas.forms import ExamplesForm
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.services import (
    accept_suggestions,
    choices,
    create_annotation,
    create_remaining,
    ignore,
    link,
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
    history = (
        observations.filter(location=location)
        .order_by("upload__requested_at")
        .values("upload__requested_at", "upload__language", "kind", "type", "shape", "format")
    )
    context = {
        "platform": platform,
        "filter": schema_filter,
        "location": location,
        "profile": profiles([location.pk], observations)[location.pk],
        "history": history,
        "annotations": platform.annotations.all(),
    }
    return render(request, "schemas/_location_detail.html", context)


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
    context = {
        "upload": upload,
        "review": review(upload) if upload.registered_at else None,
        "annotations": upload.platform.annotations.all(),
    }
    return render(request, "schemas/review.html", context)


@login_required
@require_POST
def triage(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: decide what a data point is. Returns the updated triage row."""
    location = get_object_or_404(Location.objects.select_related("platform"), pk=pk)
    action = request.POST.get("action")
    if action == "link":
        annotation = get_object_or_404(
            Annotation, pk=request.POST.get("annotation"), platform=location.platform
        )
        link(location, annotation)
    elif action == "new":
        create_annotation(location, request.POST.get("name", ""), signed_in_user(request))
    elif action == "ignore":
        ignore(location)
    elif action == "reset":
        link(location, None)
    upload_id = request.POST.get("upload") or None  # empty when triaging from the explorer
    observation = (
        Observation.objects.filter(location=location, upload_id=upload_id)
        .select_related("location", "location__annotation", "upload")
        .first()
        if upload_id
        else None
    )
    context = {
        "location": location,
        "observation": observation,
        "is_new": observation is not None and location.pk in new_in(observation.upload),
        "choices": choices(observation) if observation else [],
        "annotations": location.platform.annotations.all(),
    }
    return render(request, "schemas/_triage_row.html", context)


@login_required
@require_POST
def review_action(request: HttpRequest, pk: int) -> HttpResponse:
    upload = get_object_or_404(Upload, pk=pk)
    if request.POST.get("action") == "accept":
        linked = accept_suggestions(upload)
        messages.success(request, f"Linked {linked} data points to their suggested annotations.")
    else:
        parent = request.POST.get("parent")
        created = create_remaining(upload, signed_in_user(request), parent)
        messages.success(request, f"Created {created} new annotations.")
    return redirect("schemas:review", pk=upload.pk)
