"""The review of an upload: its data points to assign (as a tree, ``tree.py``), what changed and
what is missing, with a side panel focused on annotating. Triaging itself is ``schemas`` (the
explorer uses it too).
"""

from dataclasses import dataclass
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.values import OwnValues, own_values
from ddp_tracker.reviews.services import Review, review, triage_items
from ddp_tracker.reviews.tree import build, build_row
from ddp_tracker.schemas.examples import EXTRACTED, add_examples, as_text
from ddp_tracker.schemas.filters import SchemaFilter
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.timeline import change_details
from ddp_tracker.schemas.tree import sections
from ddp_tracker.schemas.views import panel_context

TABS = ("assign", "changed", "missing")


@dataclass(frozen=True)
class Progress:
    decided: int  # annotated, or marked as not a data point
    total: int  # the upload's data points

    @property
    def percent(self) -> int:
        return round(100 * self.decided / self.total) if self.total else 100


def progress_of(upload: Upload) -> Progress:
    points = upload.observations.filter(is_data_point=True)
    decided = points.filter(Q(location__annotation__isnull=False) | Q(location__ignored=True))
    return Progress(decided.count(), points.count())


@login_required
def upload_review(request: HttpRequest, pk: int) -> HttpResponse:
    """The review page. With htmx (the filter box), only the tree's groups."""
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    tab = request.GET.get("tab", "assign")
    tab = tab if tab in TABS else "assign"
    context: dict[str, Any] = {"upload": upload, "tab": tab, "review": None}
    if upload.registered_at:
        context |= _review_context(request, upload, tab)
    if request.headers.get("HX-Request") and tab == "assign":
        return render(request, "schemas/tree/_groups.html", context)
    return render(request, "reviews/base.html", context)


def _review_context(request: HttpRequest, upload: Upload, tab: str) -> dict[str, Any]:
    result: Review = review(upload)
    own = own_values(request, upload)
    q = request.GET.get("q", "").strip()
    hide = request.GET.get("hide") == "1"  # the annotated ones
    tree = build(upload, result.triage, own, q, annotated=not hide)
    everything = build(upload, result.triage, own) if q else tree
    platform = upload.platform_id
    return {
        "row_template": "reviews/_row.html",
        "annotating": True,  # counts of what is still to assign, Enter to annotate
        "review": result,
        "own": own,
        "q": q,
        "hide": hide,
        "tree": tree,
        "open_count": everything.open_count,
        "progress": progress_of(upload),
        "changed": sections(
            platform, [(c.observation.location, c) for c in result.changed], upload.file_name
        ),
        # missing keys of earlier single-file uploads aren't this zip's
        "missing": sections(
            platform,
            [(m.location, m) for m in result.missing],
            upload.file_name if upload.root_format != "zip" else "Single-file uploads",
        ),
    }


def review_row(request: HttpRequest, pk: int, location_pk: int) -> HttpResponse:
    """HTMX: one row of the "To assign" tree, reloaded after a change; out of band, its group's
    and root's counts, the tab's count and the progress."""
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    location = get_object_or_404(Location, pk=location_pk, platform=upload.platform)
    get_object_or_404(Observation, upload=upload, location=location)
    own = own_values(request, upload)
    row, group_path, root_path = build_row(upload, location, own)
    tree = build(upload, triage_items(upload), own)
    group = next((g for g in tree.groups if g.path == group_path), None)
    root = next((r for r in tree.roots if r.path == root_path), None)
    context = {
        "upload": upload,
        "row": row,
        "own": own,
        "group_id": group.id if group else "",
        "group_open": group.open_count if group else 0,
        "root_id": root.id if root else "",
        "root_open": root.open_count if root else 0,
        "open_count": tree.open_count,
        "progress": progress_of(upload),
        "oob": True,
    }
    return render(request, "reviews/_row.html", context)


@login_required
def review_location(request: HttpRequest, pk: int, location_pk: int) -> HttpResponse:
    """HTMX: the side panel of a row (for a list: the list and its item), in the reviewed
    upload's context; a missing location's over all uploads."""
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    location = get_object_or_404(
        Location.objects.select_related("annotation", "platform"),
        pk=location_pk,
        platform=upload.platform,
    )
    counted = Observation.objects.filter(upload__registered_at__isnull=False)
    observation = upload.observations.filter(location=location).first()
    scope = upload.observations.all() if observation else counted
    context = panel_context(location, scope, counted, SchemaFilter(), observation)
    own = own_values(request, upload)
    row = build_row(upload, location, own)[0] if observation else None
    context |= {
        "upload": upload,
        "own": own,
        "row": row,
        "own_list": _own_list(own, row.primary if row else location),
        "changed": observation is not None and location.pk in change_details(upload),
        "first_seen": context["history"].first(),
    }
    return render(request, "reviews/_panel.html", context)


def _own_list(own: OwnValues | None, location: Location) -> list[str]:
    values = own.values.get(location.path, []) if own else []
    return [as_text(value) for value in values]


@login_required
@require_POST
def review_add_examples(request: HttpRequest, pk: int, location_pk: int) -> HttpResponse:
    """HTMX: the uploader contributes some of the values found in their file, as they are, to a
    data point's public examples (marked "extracted"); returns the updated examples block. Only
    their positions are posted: the values come from the file's values, not from the browser."""
    upload = get_object_or_404(Upload, pk=pk)
    location = get_object_or_404(Location, pk=location_pk, platform=upload.platform)
    own = own_values(request, upload)
    if own is None or not own.readable:
        raise PermissionDenied
    found = own.values.get(location.path, [])
    chosen = {int(i) for i in request.POST.getlist("use") if i.isdigit()}
    values = [as_text(value) for i, value in enumerate(found) if i in chosen]
    add_examples(location, values, EXTRACTED)
    return render(request, "schemas/_examples.html", {"location": location})
