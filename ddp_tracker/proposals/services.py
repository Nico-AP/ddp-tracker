"""Suggesting, accepting and rejecting changes (``Proposal``).

``submit`` is the write views' single entry point: staff's changes apply directly, everyone
else's become open proposals. ``accept`` applies one through the curating services
(``schemas.services``, ``representations.services``) and supersedes the other open proposals
for the same target; ``reject`` records why.
"""

import copy
from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.forms.models import model_to_dict
from django.utils import timezone

from ddp_tracker.annotations.forms import AnnotationForm
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.representations.eligibility import is_eligible, metadata_candidates
from ddp_tracker.representations.forms import (
    SLOTS,
    SUBJECTS,
    VOCABULARIES,
    RepresentationForm,
)
from ddp_tracker.representations.models import MetadataRole, ObjectType, Representation
from ddp_tracker.representations.services import describe
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation, ignore, link
from ddp_tracker.users.models import User

Kind = Proposal.Kind
Status = Proposal.Status

LOCATION_KINDS = (Kind.LINK, Kind.NEW_ANNOTATION, Kind.IGNORE, Kind.UNASSIGN)
ANNOTATION_KINDS = (*LOCATION_KINDS, Kind.EDIT_ANNOTATION)  # the annotations queue
REPRESENTATION_KINDS = tuple(kind for kind in Kind if kind not in ANNOTATION_KINDS)
ANNOTATION_FIELDS = ("name", "description", "note", "pii")
REPRESENTATION_FIELDS = ("pattern", "name", "description", "note", *SLOTS)


class ProposalError(Exception):
    """A proposal that can't be made or applied (as it is now); the message says why."""


class StaleError(ProposalError):
    """The target changed since it was proposed: staff confirm before it is applied."""


def open_for(target: str, pk: int) -> Q:
    """The open suggestions about ``target`` ``pk`` (``proposals:for``): a location's annotation,
    an annotation, a representation, or a location's representations (new ones name the
    location, edits and deletions their representation)."""
    about = {
        "location": Q(location=pk, kind__in=LOCATION_KINDS),
        "annotation": Q(annotation=pk),
        "representation": Q(representation=pk),
        "location-representations": Q(kind__in=REPRESENTATION_KINDS)
        & (Q(location=pk) | Q(representation__location=pk)),
    }[target]
    return about & Q(status=Status.OPEN)


# --- suggesting --------------------------------------------------------------------------------


def submit(user: User, kind: str, *, comment: str = "", **targets: Any) -> Proposal | None:
    """Staff: apply the change now (``None``). Everyone else: an open proposal, replacing the
    user's own open one for the same target. ``targets`` are the model's target fields and
    ``values`` (the proposed fields). Raises ``ProposalError`` for an invalid change."""
    proposal = Proposal(kind=kind, proposed_by=user, comment=comment.strip(), **targets)
    proposal.platform = _platform(proposal)
    base = snapshot(proposal)
    _validate(proposal, user)
    if user.is_staff:
        with transaction.atomic():
            _apply(proposal, user)
        return None
    with transaction.atomic():
        own = Proposal.objects.filter(_same_target(proposal), proposed_by=user, status=Status.OPEN)
        own.update(status=Status.WITHDRAWN, reason="Replaced by a newer suggestion.")
        proposal.base = base
        proposal.save()
    return proposal


def _platform(proposal: Proposal) -> Any:  # noqa: ANN401 - a Platform or None
    if proposal.location is not None:
        return proposal.location.platform
    if proposal.annotation is not None:
        return proposal.annotation.platform
    if proposal.representation is not None:
        return proposal.representation.location.platform
    return None


def _validate(proposal: Proposal, user: User) -> None:
    """The change must make sense now (the forms' own rules, for fields and vocabulary)."""
    VALIDATE[proposal.kind](proposal, user)


def _check_location(proposal: Proposal, user: User) -> None:
    location = _need(proposal.location, "a data point")
    if proposal.kind == Kind.LINK:
        annotation = _need(proposal.annotation, "an annotation")
        if annotation.platform_id != location.platform_id:
            msg = "The annotation belongs to another platform."
            raise ProposalError(msg)
    elif proposal.kind == Kind.NEW_ANNOTATION:
        _valid(AnnotationForm(data=proposal.values))
        _also(proposal, location)


def _also(proposal: Proposal, location: Location) -> list[Location]:
    """The other locations a new annotation is also for (``values["also"]``: similar paths, the
    same data point), on the platform. Those decided in the meantime (annotated, not a data
    point) are left as they are."""
    wanted = set(proposal.values.get("also") or []) - {location.pk}
    found = list(Location.objects.filter(pk__in=wanted, platform=location.platform_id))
    if len(found) != len(wanted):
        msg = "A path to annotate together with it isn't a data point of this platform."
        raise ProposalError(msg)
    return [other for other in found if other.annotation_id is None and not other.ignored]


def _check_annotation(proposal: Proposal, user: User) -> None:
    annotation = _need(proposal.annotation, "an annotation")
    # on a copy: a ModelForm's validation writes the values onto its instance
    _valid(AnnotationForm(data=proposal.values, instance=copy.copy(annotation)))


def _check_representation(proposal: Proposal, user: User) -> None:
    if proposal.kind == Kind.NEW_REPRESENTATION:
        location = _need(proposal.location, "a data point")
        if not is_eligible(location):
            msg = "This data point can't have representations."
            raise ProposalError(msg)
    _valid(_representation_form(proposal, user, copy.copy(proposal.representation)))
    _metadata_rows(proposal, user)


def _representation_form(
    proposal: Proposal, user: User, instance: Representation | None
) -> RepresentationForm:
    """The proposed fields on ``instance`` (a new one if ``None``), validated against the
    proposed metadata links (``values["metadata"]``, which replace the saved ones)."""
    instance = instance or Representation()
    if "metadata" in proposal.values:
        instance.described = [row.get("subject", "") for row in proposal.values["metadata"]]
    return RepresentationForm(data=proposal.values, instance=instance, user=user)


def _anchor(proposal: Proposal) -> Location:
    """The location the representation is (or will be) of."""
    if proposal.representation is not None:
        return proposal.representation.location
    return _need(proposal.location, "a data point")


def _metadata_rows(proposal: Proposal, user: User) -> list[tuple[str, MetadataRole, Location]]:
    """A representation's metadata links (``values["metadata"]``): subjects its pattern
    fills, roles offered to ``user``, data points below the representation's location."""
    rows = proposal.values.get("metadata") or []
    if not rows:
        return []
    candidates = metadata_candidates(_anchor(proposal))
    subjects = SUBJECTS.get(proposal.values.get("pattern", ""), ())
    roles = MetadataRole.for_user(user)
    found = []
    for row in rows:
        role = roles.filter(pk=row.get("role") or 0).first()
        location = candidates.filter(pk=row.get("location") or 0).first()
        if row.get("subject") not in subjects or role is None or location is None:
            msg = f"A metadata row can't be used as it is: {row}."
            raise ProposalError(msg)
        found.append((row["subject"], role, location))
    return found


def _check_delete_representation(proposal: Proposal, user: User) -> None:
    representation = _need(proposal.representation, "a representation")
    proposal.values = {"representation": str(representation)}  # shown once it is gone


VALIDATE: dict[str, Callable[[Proposal, User], None]] = {
    Kind.LINK: _check_location,
    Kind.NEW_ANNOTATION: _check_location,
    Kind.IGNORE: _check_location,
    Kind.UNASSIGN: _check_location,
    Kind.EDIT_ANNOTATION: _check_annotation,
    Kind.NEW_REPRESENTATION: _check_representation,
    Kind.EDIT_REPRESENTATION: _check_representation,
    Kind.DELETE_REPRESENTATION: _check_delete_representation,
}


def _need[T](value: T | None, what: str) -> T:
    """``value``, which the kind requires (a location, an annotation …)."""
    if value is None:
        msg = f"This needs {what}."
        raise ProposalError(msg)
    return value


def _valid(form: Any) -> None:  # noqa: ANN401 - a Django form
    if not form.is_valid():
        errors = [
            f"{field}: {message}" for field, messages in form.errors.items() for message in messages
        ]
        raise ProposalError("; ".join(errors))


# Proposals about the same thing: kinds that compete, and the fields that must match
_TARGETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    **dict.fromkeys(LOCATION_KINDS, (LOCATION_KINDS, ("location",))),
    Kind.EDIT_ANNOTATION: ((Kind.EDIT_ANNOTATION,), ("annotation",)),
    Kind.EDIT_REPRESENTATION: ((Kind.EDIT_REPRESENTATION,), ("representation",)),
    Kind.DELETE_REPRESENTATION: ((Kind.DELETE_REPRESENTATION,), ("representation",)),
}


def _same_target(proposal: Proposal) -> Q:
    """Proposals about the same thing (one open per user; accepting one supersedes the rest).
    A new representation is about nothing else."""
    if proposal.kind not in _TARGETS:
        return Q(pk=proposal.pk)
    kinds, fields = _TARGETS[proposal.kind]
    return Q(kind__in=kinds, **{field: getattr(proposal, f"{field}_id") for field in fields})


def snapshot(proposal: Proposal) -> dict[str, Any]:
    """The target's current state, as far as the proposal is about it."""
    kind = proposal.kind
    if kind in LOCATION_KINDS and proposal.location is not None:
        location = proposal.location
        return {"annotation": location.annotation_id, "ignored": location.ignored}
    if kind == Kind.EDIT_ANNOTATION and proposal.annotation is not None:
        return model_to_dict(proposal.annotation, fields=list(ANNOTATION_FIELDS))
    if kind == Kind.EDIT_REPRESENTATION and proposal.representation is not None:
        representation = proposal.representation
        return model_to_dict(representation, fields=list(REPRESENTATION_FIELDS)) | {
            "metadata": metadata_of(representation)
        }
    if kind == Kind.DELETE_REPRESENTATION:
        return {"exists": proposal.representation_id is not None}
    return {}


def metadata_of(representation: Representation) -> list[dict[str, Any]]:
    """A representation's metadata links as a proposal keeps them, in a stable order."""
    links = representation.metadata_links.values("subject", "role", "location")
    return _in_order([dict(link) for link in links])


def _in_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (row.get("subject", ""), row.get("location") or 0, row.get("role") or 0),
    )


def is_stale(proposal: Proposal) -> bool:
    return proposal.is_open and snapshot(proposal) != proposal.base


# --- deciding -----------------------------------------------------------------------------------


def _staff(user: User) -> None:
    if not user.is_staff:
        raise PermissionDenied


def accept(proposal: Proposal, staff: User, *, stale_ok: bool = False) -> None:
    """Apply ``proposal`` and supersede the other open ones for the same target. A stale one
    (the target changed since) raises ``StaleError`` unless ``stale_ok``."""
    _staff(staff)
    if not proposal.is_open:
        msg = "This suggestion is decided already."
        raise ProposalError(msg)
    if is_stale(proposal) and not stale_ok:
        msg = "This changed since it was suggested."
        raise StaleError(msg)
    _validate(proposal, staff)  # as it is now, with the approved vocabulary
    with transaction.atomic():
        _apply(proposal, staff)
        others = Proposal.objects.filter(_same_target(proposal), status=Status.OPEN).exclude(
            pk=proposal.pk
        )
        now = timezone.now()
        others.update(
            status=Status.SUPERSEDED,
            decided_by=staff,
            decided_at=now,
            reason="Another suggestion for the same was accepted.",
        )
        _decide(proposal, staff, Status.ACCEPTED, now)  # the same moment: superseded_by


def reject(proposal: Proposal, staff: User, reason: str) -> None:
    _staff(staff)
    if not proposal.is_open:
        msg = "This suggestion is decided already."
        raise ProposalError(msg)
    proposal.reason = reason.strip()
    _decide(proposal, staff, Status.REJECTED)


def withdraw(proposal: Proposal, user: User) -> None:
    if proposal.proposed_by_id != user.pk or not proposal.is_open:
        raise PermissionDenied
    proposal.status = Status.WITHDRAWN
    proposal.save(update_fields=["status"])


def _decide(proposal: Proposal, staff: User, status: str, now: datetime | None = None) -> None:
    proposal.status = status
    proposal.decided_by = staff
    proposal.decided_at = now or timezone.now()
    proposal.save()


# --- applying -----------------------------------------------------------------------------------


def _apply(proposal: Proposal, actor: User) -> None:
    """Make the change, as the proposer's (staff: their own)."""
    author = proposal.proposed_by or actor
    try:
        APPLY[proposal.kind](proposal, author, actor)
    except (ValidationError, IntegrityError) as error:
        raise ProposalError(str(error)) from error


def _link(proposal: Proposal, author: User, actor: User) -> None:
    link(_need(proposal.location, "a data point"), proposal.annotation)


def _new_annotation(proposal: Proposal, author: User, actor: User) -> None:
    """The annotation, for the location and the similar paths it is also for (``also``)."""
    values = proposal.values
    location = _need(proposal.location, "a data point")
    also = _also(proposal, location)  # still undecided ones only
    annotation = create_annotation(
        location,
        values.get("name", ""),
        author,
        description=values.get("description", ""),
        note=values.get("note", ""),
        pii=bool(values.get("pii")),
    )
    for other in also:
        link(other, annotation)


def _ignore(proposal: Proposal, author: User, actor: User) -> None:
    ignore(_need(proposal.location, "a data point"))


def _unassign(proposal: Proposal, author: User, actor: User) -> None:
    link(_need(proposal.location, "a data point"), None)


def _edit_annotation(proposal: Proposal, author: User, actor: User) -> None:
    form = AnnotationForm(data=proposal.values, instance=proposal.annotation)
    _valid(form)
    annotation = form.save(commit=False)
    annotation.updated_by = author
    annotation.save()


def _representation(proposal: Proposal, author: User, actor: User) -> None:
    """Create or edit it; its metadata links become the proposed ones (``values["metadata"]``,
    an edit without it keeps them)."""
    form = _representation_form(proposal, actor, proposal.representation)
    _valid(form)
    rows = _metadata_rows(proposal, actor)
    representation = form.save(commit=False)
    if representation.pk is None:  # new: the location it is for (never changed afterwards)
        representation.location = _need(proposal.location, "a data point")
    representation.updated_by = author
    representation.save()
    if "metadata" in proposal.values:
        wanted = {(subject, role.pk, location.pk) for subject, role, location in rows}
        for link in representation.metadata_links.all():
            if (link.subject, link.role_id, link.location_id) not in wanted:
                link.delete()
        kept = set(representation.metadata_links.values_list("subject", "role", "location"))
        for subject, role, location in rows:
            if (subject, role.pk, location.pk) not in kept:
                describe(representation, location, role, subject)
    proposal.representation = representation


def _delete_representation(proposal: Proposal, author: User, actor: User) -> None:
    _need(proposal.representation, "a representation").delete()
    proposal.representation = None  # gone; ``values["representation"]`` says what it was


APPLY: dict[str, Callable[[Proposal, User, User], None]] = {
    Kind.LINK: _link,
    Kind.NEW_ANNOTATION: _new_annotation,
    Kind.IGNORE: _ignore,
    Kind.UNASSIGN: _unassign,
    Kind.EDIT_ANNOTATION: _edit_annotation,
    Kind.NEW_REPRESENTATION: _representation,
    Kind.EDIT_REPRESENTATION: _representation,
    Kind.DELETE_REPRESENTATION: _delete_representation,
}


# --- showing ------------------------------------------------------------------------------------


def changes(proposal: Proposal) -> list[tuple[str, str, str]]:
    """What the proposal changes, as ``(field, now, proposed)`` in words."""
    kind, values = proposal.kind, proposal.values
    if kind in LOCATION_KINDS:
        now = _assignment(proposal.base)
        proposed: dict[str, str] = {
            Kind.LINK: str(proposal.annotation),
            Kind.NEW_ANNOTATION: f"new: {values.get('name', '')}",
            Kind.IGNORE: "not a data point",
            Kind.UNASSIGN: "none",
        }
        rows = [("Annotation", now, proposed[kind])]
        if kind == Kind.NEW_ANNOTATION:
            rows += [
                (field.capitalize(), "", values.get(field, "")) for field in ("description", "note")
            ]
            also = Location.objects.filter(pk__in=values.get("also") or []).order_by("path")
            rows += [("Also for", "", other.path) for other in also]
            if values.get("pii"):
                rows.append(("PII", "", "yes"))
        return [row for row in rows if row[1] or row[2]]
    if kind in {Kind.EDIT_ANNOTATION, Kind.EDIT_REPRESENTATION, Kind.NEW_REPRESENTATION}:
        fields = ANNOTATION_FIELDS if kind == Kind.EDIT_ANNOTATION else REPRESENTATION_FIELDS
        before = proposal.base
        rows = [
            (_label(field), _shown(field, before.get(field)), _shown(field, values.get(field)))
            for field in fields
            if _shown(field, before.get(field)) != _shown(field, values.get(field))
        ]
        if kind == Kind.NEW_REPRESENTATION and proposal.location is not None:
            rows.append(("Of", "", proposal.location.path))
        if "metadata" in values:
            saved, wanted = before.get("metadata") or [], values["metadata"]
            rows += [("Metadata", _metadata_row(row), "none") for row in saved if row not in wanted]
            rows += [("Metadata", "", _metadata_row(row)) for row in wanted if row not in saved]
        return rows
    return [("Representation", values.get("representation", ""), "none")]


def _metadata_row(row: dict[str, Any]) -> str:
    """``{"subject": "activity", "role": 3, "location": 7}`` in words: "…/[]/Date: when of the
    activity"."""
    role = MetadataRole.objects.filter(pk=row.get("role") or 0).first()
    location = Location.objects.filter(pk=row.get("location") or 0).first()
    where = location.path if location else "(deleted)"
    return f"{where}: {role or '(deleted)'} of the {row.get('subject', '')}"


def superseded_by(proposal: Proposal) -> QuerySet[Proposal]:
    """The suggestions accepting ``proposal`` superseded (``accept``: same target, same moment)."""
    if proposal.status != Status.ACCEPTED:
        return Proposal.objects.none()
    return Proposal.objects.filter(
        _same_target(proposal), status=Status.SUPERSEDED, decided_at=proposal.decided_at
    ).exclude(pk=proposal.pk)


def group_key(proposal: Proposal) -> tuple[str, int]:
    """What a suggestion is about, for staff's queues to show them together: its location (an
    annotation suggestion's; a representation's list item), or the annotation it edits."""
    if proposal.kind == Kind.EDIT_ANNOTATION:
        return ("annotation", proposal.annotation_id or 0)
    if proposal.location_id is None and proposal.representation is not None:
        return ("location", proposal.representation.location_id)
    return ("location", proposal.location_id or 0)


def assignment_of(location: Location) -> str:
    """A location's annotation now, in words ("none", "not a data point", its name)."""
    return _assignment({"annotation": location.annotation_id, "ignored": location.ignored})


def _assignment(base: dict[str, Any]) -> str:
    if base.get("ignored"):
        return "not a data point"
    if base.get("annotation"):
        found = Annotation.objects.filter(pk=base["annotation"]).first()
        return str(found) if found else "(deleted)"
    return "none"


def _label(field: str) -> str:
    return "PII" if field == "pii" else field.capitalize()


def _shown(field: str, value: Any) -> str:  # noqa: ANN401
    """A form value in words (vocabulary terms by name)."""
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if field in SLOTS:
        model = ObjectType if field == "target" else VOCABULARIES[field]
        term = model.objects.filter(pk=value).first()
        return str(term) if term else str(value)
    return str(value)
