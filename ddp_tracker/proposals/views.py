"""Staff's queues of open suggestions (annotations by platform, representations), a user's own
suggestions, deciding one at a time, and the lists of open suggestions in the panels."""

from dataclasses import dataclass, field
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import (
    ANNOTATION_KINDS,
    REPRESENTATION_KINDS,
    ProposalError,
    StaleError,
    accept,
    assignment_of,
    changes,
    group_key,
    is_stale,
    open_for,
    reject,
    superseded_by,
    withdraw,
)
from ddp_tracker.schemas.models import Location
from ddp_tracker.users.auth import signed_in_user

Status = Proposal.Status


def _entries(proposals: QuerySet[Proposal]) -> list[dict[str, Any]]:
    """Proposals with what they change, for the templates."""
    proposals = proposals.select_related(
        "proposed_by",
        "decided_by",
        "location",
        "annotation",
        "representation__location",
    )
    return [{"proposal": p, "changes": changes(p), "stale": is_stale(p)} for p in proposals]


@dataclass
class ProposalGroup:
    """Suggestions about the same thing (``services.group_key``), shown together in a queue: a
    location (with its annotation, or its representations, now) or an annotation."""

    key: tuple[str, int]
    location: Location | None = None
    annotation: Annotation | None = None
    now: str = ""
    entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"group-{self.key[0]}-{self.key[1]}"

    @property
    def sort_key(self) -> str:
        return self.location.path if self.location else str(self.annotation)


def _grouped(
    proposals: QuerySet[Proposal], *, representations: bool = False
) -> list[ProposalGroup]:
    """Staff's queue, one group per location or annotation (by path or name); oldest first
    within a group."""
    groups: dict[tuple[str, int], ProposalGroup] = {}
    for entry in _entries(proposals.order_by("created_at")):
        proposal = entry["proposal"]
        key = group_key(proposal)
        if key not in groups:
            if key[0] == "annotation":
                annotation = proposal.annotation
                groups[key] = ProposalGroup(key, annotation=annotation)
            else:
                location = Location.objects.select_related("annotation").get(pk=key[1])
                now = (
                    ", ".join(str(r) for r in location.representations.all()) or "none"
                    if representations
                    else assignment_of(location)
                )
                groups[key] = ProposalGroup(key, location=location, now=now)
        groups[key].entries.append(entry)
    return sorted(groups.values(), key=lambda group: group.sort_key.casefold())


def _open(kinds: tuple[str, ...]) -> QuerySet[Proposal]:
    return Proposal.objects.filter(status=Status.OPEN, kind__in=kinds)


@staff_member_required
def annotation_queue(request: HttpRequest) -> HttpResponse:
    """Open annotation suggestions, one platform at a time (the one with the most first)."""
    counts = (
        _open(ANNOTATION_KINDS)
        .values("platform__slug", "platform__name")
        .annotate(count=Count("id"))
        .order_by("-count", "platform__name")
    )
    platforms = [(c["platform__slug"], c["platform__name"], c["count"]) for c in counts]
    chosen = request.GET.get("platform") or (platforms[0][0] if platforms else "")
    platform = Platform.objects.filter(slug=chosen).first()
    proposals = (
        _open(ANNOTATION_KINDS).filter(platform=platform) if platform else Proposal.objects.none()
    )
    context = {
        "title": "Annotation suggestions",
        "queue": "annotations",
        "platforms": platforms,
        "platform": platform,
        "groups": _grouped(proposals),
    }
    return render(request, "proposals/queue.html", context)


@staff_member_required
def representation_queue(request: HttpRequest) -> HttpResponse:
    context = {
        "title": "Representation suggestions",
        "queue": "representations",
        "groups": _grouped(_open(REPRESENTATION_KINDS), representations=True),
    }
    return render(request, "proposals/queue.html", context)


@login_required
def mine(request: HttpRequest) -> HttpResponse:
    """The signed-in user's suggestions, newest first, with how they were decided."""
    proposals = Proposal.objects.filter(proposed_by=signed_in_user(request)).order_by("-created_at")
    return render(request, "proposals/mine.html", {"entries": _entries(proposals)})


def _decided(request: HttpRequest, proposal: Proposal, error: str = "") -> HttpResponse:
    """HTMX: the proposal's entry after a decision; the target's row and panels reload."""
    proposal.refresh_from_db()
    # decided in a side panel or a queue's group: still without the path, which they show
    hide_target = request.POST.get("hide_target") == "1"
    context = {
        "entry": {"proposal": proposal, "changes": changes(proposal), "stale": is_stale(proposal)},
        "error": error,
        "hide_target": hide_target,
        "in_queue": request.POST.get("in_queue") == "1",
    }
    html = render_to_string("proposals/_entry.html", context, request)
    if context["in_queue"]:  # the ones it superseded, next to it in the queue, update too
        for entry in _entries(superseded_by(proposal)):
            sibling = {"entry": entry, "hide_target": hide_target, "in_queue": True, "oob": True}
            html += render_to_string("proposals/_entry.html", sibling, request)
    response = HttpResponse(html)
    targets = []
    if proposal.location_id:
        targets.append(f"triaged-{proposal.location_id}")
    if proposal.kind in REPRESENTATION_KINDS and (represented := _represented(proposal)):
        targets.append(f"representations-changed-{represented}")
    if targets:
        response["HX-Trigger"] = ", ".join(targets)
    return response


@staff_member_required
@require_POST
def decide(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    """Accept (``stale=1`` to confirm a stale one) or reject (with a ``reason``)."""
    proposal = get_object_or_404(Proposal, pk=pk)
    staff = signed_in_user(request)
    try:
        if action == "accept":
            accept(proposal, staff, stale_ok=request.POST.get("stale") == "1")
        else:
            reject(proposal, staff, request.POST.get("reason", ""))
    except StaleError:
        return _decided(request, proposal, "This changed since it was suggested: accept anyway?")
    except ProposalError as error:
        return _decided(request, proposal, str(error))
    return _decided(request, proposal)


def _represented(proposal: Proposal) -> int | None:
    """The location whose representations the proposal is about: the representation's (the new
    one's is ``location``; a deleted one's is gone, and so is the event's panel)."""
    if proposal.representation is not None:
        return proposal.representation.location_id
    return proposal.location_id


@login_required
@require_POST
def withdraw_view(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(Proposal, pk=pk)
    withdraw(proposal, signed_in_user(request))
    return _decided(request, proposal)


# the lists the side panels load (proposals/_marker.html), about the panel's location
PANEL_TARGETS = ("location", "location-representations")


def for_target(request: HttpRequest, target: str, pk: int) -> HttpResponse:
    """HTMX: the open suggestions for a location's annotation, an annotation, a representation or
    a location's representations (in panels and on their pages). Only their proposer and staff
    see them (``Proposal.objects.visible_to``); that some are open is public (the markers)."""
    proposals = Proposal.objects.visible_to(request.user).filter(open_for(target, pk))
    context = {
        "entries": _entries(proposals),
        # in a location's side panel the location is clear from the context: no path
        "hide_target": target in PANEL_TARGETS,
    }
    return render(request, "proposals/_for_target.html", context)
