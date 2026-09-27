"""Staff's queues of open suggestions (annotations by platform, representations), a user's own
suggestions, deciding one at a time, and the lists of open suggestions in the panels."""

from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import (
    ANNOTATION_KINDS,
    REPRESENTATION_KINDS,
    ProposalError,
    StaleError,
    accept,
    changes,
    is_stale,
    reject,
    withdraw,
)
from ddp_tracker.users.auth import signed_in_user

Status = Proposal.Status


def _entries(proposals: QuerySet[Proposal]) -> list[dict[str, Any]]:
    """Proposals with what they change, for the templates."""
    proposals = proposals.select_related(
        "proposed_by", "decided_by", "location", "annotation", "representation", "role"
    )
    return [{"proposal": p, "changes": changes(p), "stale": is_stale(p)} for p in proposals]


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
        "entries": _entries(proposals),
    }
    return render(request, "proposals/queue.html", context)


@staff_member_required
def representation_queue(request: HttpRequest) -> HttpResponse:
    context = {
        "title": "Representation suggestions",
        "queue": "representations",
        "entries": _entries(_open(REPRESENTATION_KINDS)),
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
    context = {
        "entry": {"proposal": proposal, "changes": changes(proposal), "stale": is_stale(proposal)},
        "error": error,
    }
    response = render(request, "proposals/_entry.html", context)
    targets = []
    if proposal.location_id:
        targets.append(f"triaged-{proposal.location_id}")
    if proposal.annotation_id:
        targets.append(f"representations-changed-{proposal.annotation_id}")
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


@login_required
@require_POST
def withdraw_view(request: HttpRequest, pk: int) -> HttpResponse:
    proposal = get_object_or_404(Proposal, pk=pk)
    withdraw(proposal, signed_in_user(request))
    return _decided(request, proposal)


def for_target(request: HttpRequest, target: str, pk: int) -> HttpResponse:
    """HTMX: the open suggestions for a location, an annotation or a representation (in panels
    and on their pages). Public: suggestions are visible to everyone."""
    field = {
        "location": "location",
        "annotation": "annotation",
        "representation": "representation",
    }[target]
    proposals = Proposal.objects.filter(Q(**{field: pk}), status=Status.OPEN)
    return render(request, "proposals/_for_target.html", {"entries": _entries(proposals)})
