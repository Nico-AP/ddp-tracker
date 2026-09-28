import copy
from datetime import date
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.html import escape
from django.views.decorators.http import require_POST

from ddp_tracker.annotations.forms import AnnotationForm
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import ANNOTATION_FIELDS, ProposalError, submit
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.users.auth import signed_in_user


def annotation_list(request: HttpRequest, slug: str) -> HttpResponse:
    platform = get_object_or_404(Platform, slug=slug)
    annotations = platform.annotations.annotate(
        location_count=Count("locations", distinct=True),
        last_seen=Max("locations__observations__upload__requested_at"),
    ).order_by("name")
    return render(
        request,
        "annotations/annotation_list.html",
        {"platform": platform, "annotations": annotations},
    )


def annotation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    annotation = get_object_or_404(Annotation.objects.select_related("platform"), pk=pk)
    return render(request, "annotations/annotation_detail.html", _detail_context(annotation))


def annotation_modal(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: the annotation page's content, in the shared modal."""
    annotation = get_object_or_404(Annotation.objects.select_related("platform"), pk=pk)
    return render(request, "annotations/_annotation_modal.html", _detail_context(annotation))


def _detail_context(annotation: Annotation) -> dict[str, Any]:
    """The annotation and its locations (recent first), each with where and how it was seen."""
    all_locations = list(annotation.locations.all())
    observations = Observation.objects.filter(upload__registered_at__isnull=False)
    found = profiles((location.pk for location in all_locations), observations)
    locations: list[dict[str, Any]] = []
    for location in all_locations:
        seen = location.observations.values("upload__language", "format").distinct()
        languages = sorted({row["upload__language"] or "unknown" for row in seen})
        formats = sorted({row["format"] for row in seen if row["format"]})
        locations.append(
            {
                "location": location,
                "profile": found[location.pk],
                "languages": languages,
                "formats": formats,
            }
        )
    locations.sort(
        key=lambda row: row["profile"].last_seen or date.min, reverse=True
    )  # recent first
    open_suggestions = annotation.proposals.filter(status=Proposal.Status.OPEN).count()
    return {"annotation": annotation, "locations": locations, "open_suggestions": open_suggestions}


def annotation_details(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX partial: the annotation's description block (public)."""
    annotation = get_object_or_404(Annotation, pk=pk)
    return render(request, "annotations/_details.html", {"annotation": annotation})


@login_required
def annotation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX partial: the edit form; a valid POST returns the updated description block."""
    annotation = get_object_or_404(Annotation, pk=pk)
    form = AnnotationForm(request.POST or None, instance=copy.copy(annotation))
    if request.method == "POST" and form.is_valid():
        # staff: saved; everyone else: a suggestion for staff to review (proposals)
        values = {field: form.cleaned_data[field] for field in ANNOTATION_FIELDS}
        try:
            proposal = submit(
                signed_in_user(request),
                Proposal.Kind.EDIT_ANNOTATION,
                annotation=annotation,
                values=values,
                comment=request.POST.get("comment", ""),
            )
        except ProposalError as error:
            form.add_error(None, str(error))
        else:
            annotation.refresh_from_db()
            context = {"annotation": annotation, "suggested": proposal is not None}
            return render(request, "annotations/_details.html", context)
    return render(
        request, "annotations/_annotation_form.html", {"annotation": annotation, "form": form}
    )


@login_required
@require_POST
def unlink(request: HttpRequest, pk: int) -> HttpResponse:
    """Detach a location from its annotation."""
    location = get_object_or_404(Location, pk=pk)
    try:
        proposal = submit(signed_in_user(request), Proposal.Kind.UNASSIGN, location=location)
    except ProposalError as error:
        return HttpResponse(f'<p class="muted">{escape(error)}</p>')
    if proposal is not None:
        return HttpResponse('<p class="muted">Suggested; staff will review it.</p>')
    return HttpResponse('<p class="muted">Unlinked.</p>')
