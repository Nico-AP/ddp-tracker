"""Suggesting, accepting and rejecting changes (``Proposal``).

``submit`` is the write views' single entry point: staff's changes apply directly, everyone
else's become open proposals. ``accept`` applies one through the curating services
(``schemas.services``, ``representations.services``) and supersedes the other open proposals
for the same target; ``reject`` records why.
"""

import copy
from collections.abc import Callable
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.utils import timezone

from ddp_tracker.annotations.forms import AnnotationForm
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.representations.forms import (
    SLOTS,
    SUBJECTS,
    VOCABULARIES,
    DescribeForm,
    RepresentationForm,
)
from ddp_tracker.representations.models import MetadataRole, ObjectType
from ddp_tracker.representations.services import describe, represent
from ddp_tracker.schemas.services import create_annotation, ignore, link
from ddp_tracker.users.models import User

Kind = Proposal.Kind
Status = Proposal.Status

LOCATION_KINDS = (Kind.LINK, Kind.NEW_ANNOTATION, Kind.IGNORE, Kind.UNASSIGN)
ANNOTATION_KINDS = (*LOCATION_KINDS, Kind.EDIT_ANNOTATION)  # the annotations queue
REPRESENTATION_KINDS = tuple(kind for kind in Kind if kind not in ANNOTATION_KINDS)
REPRESENTATION_FIELDS = ("pattern", "name", "description", "note", *SLOTS)


class ProposalError(Exception):
    """A proposal that can't be made or applied (as it is now); the message says why."""


class StaleError(ProposalError):
    """The target changed since it was proposed: staff confirm before it is applied."""


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


def _check_annotation(proposal: Proposal, user: User) -> None:
    annotation = _need(proposal.annotation, "an annotation")
    # on a copy: a ModelForm's validation writes the values onto its instance
    _valid(AnnotationForm(data=proposal.values, instance=copy.copy(annotation)))


def _check_representation(proposal: Proposal, user: User) -> None:
    instance = None
    if proposal.kind == Kind.EDIT_REPRESENTATION:
        instance = copy.copy(_need(proposal.representation, "a representation"))
    _valid(RepresentationForm(data=proposal.values, instance=instance, user=user))
    if proposal.values.get("relation"):
        _need(proposal.annotation, "an annotation")
    _metadata_rows(proposal, user)


def _metadata_rows(proposal: Proposal, user: User) -> list[tuple[str, MetadataRole, Annotation]]:
    """A new representation's metadata links (``values["metadata"]``): subjects its pattern
    fills, roles offered to ``user``, annotations that exist."""
    rows = proposal.values.get("metadata") or []
    subjects = SUBJECTS.get(proposal.values.get("pattern", ""), ())
    roles = MetadataRole.for_user(user)
    found = []
    for row in rows:
        role = roles.filter(pk=row.get("role") or 0).first()
        annotation = Annotation.objects.filter(pk=row.get("annotation") or 0).first()
        if row.get("subject") not in subjects or role is None or annotation is None:
            msg = f"A metadata row can't be used as it is: {row}."
            raise ProposalError(msg)
        found.append((row["subject"], role, annotation))
    return found


def _check_entity_link(proposal: Proposal, user: User) -> None:
    representation = _need(proposal.representation, "a representation")
    annotation = _need(proposal.annotation, "an annotation")
    linked = representation.annotations.filter(pk=annotation.pk).exists()
    if linked == (proposal.kind == Kind.REPRESENT):
        msg = "Already linked." if linked else "Not linked."
        raise ProposalError(msg)


def _check_describe(proposal: Proposal, user: User) -> None:
    _need(proposal.representation, "a representation")
    data = {
        "representation": proposal.representation_id,
        "role": proposal.role_id,
        "subject": proposal.subject,
    }
    annotation = _need(proposal.annotation, "an annotation")
    _valid(DescribeForm(data=data, annotation=annotation, user=user))


def _check_undescribe(proposal: Proposal, user: User) -> None:
    metadata = _need(proposal.metadata, "a metadata link")
    proposal.values = {"link": str(metadata)}  # shown once the link is gone


VALIDATE: dict[str, Callable[[Proposal, User], None]] = {
    Kind.LINK: _check_location,
    Kind.NEW_ANNOTATION: _check_location,
    Kind.IGNORE: _check_location,
    Kind.UNASSIGN: _check_location,
    Kind.EDIT_ANNOTATION: _check_annotation,
    Kind.NEW_REPRESENTATION: _check_representation,
    Kind.EDIT_REPRESENTATION: _check_representation,
    Kind.REPRESENT: _check_entity_link,
    Kind.UNREPRESENT: _check_entity_link,
    Kind.DESCRIBE: _check_describe,
    Kind.UNDESCRIBE: _check_undescribe,
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
    **dict.fromkeys(
        (Kind.REPRESENT, Kind.UNREPRESENT),
        ((Kind.REPRESENT, Kind.UNREPRESENT), ("annotation", "representation")),
    ),
    Kind.DESCRIBE: ((Kind.DESCRIBE,), ("annotation", "representation", "role", "subject")),
    Kind.UNDESCRIBE: ((Kind.UNDESCRIBE,), ("metadata",)),
}


def _same_target(proposal: Proposal) -> Q:
    """Proposals about the same thing (one open per user; accepting one supersedes the rest).
    A new representation is about nothing else."""
    if proposal.kind not in _TARGETS:
        return Q(pk=proposal.pk)
    kinds, fields = _TARGETS[proposal.kind]
    match = {
        field: getattr(proposal, field if field == "subject" else f"{field}_id") for field in fields
    }
    return Q(kind__in=kinds, **match)


def snapshot(proposal: Proposal) -> dict[str, Any]:
    """The target's current state, as far as the proposal is about it."""
    kind = proposal.kind
    if kind in LOCATION_KINDS and proposal.location is not None:
        location = proposal.location
        return {"annotation": location.annotation_id, "ignored": location.ignored}
    if kind == Kind.EDIT_ANNOTATION and proposal.annotation is not None:
        return model_to_dict(proposal.annotation, fields=["name", "description", "note"])
    if kind == Kind.EDIT_REPRESENTATION and proposal.representation is not None:
        return model_to_dict(proposal.representation, fields=list(REPRESENTATION_FIELDS))
    if kind in {Kind.REPRESENT, Kind.UNREPRESENT} and proposal.representation is not None:
        linked = proposal.representation.annotations.filter(pk=proposal.annotation_id or 0)
        return {"linked": linked.exists()}
    if kind == Kind.UNDESCRIBE:
        return {"exists": proposal.metadata_id is not None}
    return {}


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
        _decide(proposal, staff, Status.ACCEPTED)


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


def _decide(proposal: Proposal, staff: User, status: str) -> None:
    proposal.status = status
    proposal.decided_by = staff
    proposal.decided_at = timezone.now()
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
    values = proposal.values
    create_annotation(
        _need(proposal.location, "a data point"),
        values.get("name", ""),
        author,
        description=values.get("description", ""),
        note=values.get("note", ""),
    )


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
    form = RepresentationForm(data=proposal.values, instance=proposal.representation, user=actor)
    _valid(form)
    representation = form.save(commit=False)
    representation.updated_by = author
    representation.save()
    form.save_m2m()
    relation = proposal.values.get("relation")
    if relation == "represents":
        represent(representation, _need(proposal.annotation, "an annotation"))
    elif relation == "describes":
        describe(
            representation,
            _need(proposal.annotation, "an annotation"),
            _need(proposal.role, "a role"),
            proposal.subject,
        )
    for subject, role, annotation in _metadata_rows(proposal, actor):
        describe(representation, annotation, role, subject)
    proposal.representation = representation


def _represent(proposal: Proposal, author: User, actor: User) -> None:
    represent(
        _need(proposal.representation, "a representation"),
        _need(proposal.annotation, "an annotation"),
    )


def _describe(proposal: Proposal, author: User, actor: User) -> None:
    describe(
        _need(proposal.representation, "a representation"),
        _need(proposal.annotation, "an annotation"),
        _need(proposal.role, "a role"),
        proposal.subject,
    )


def _unrepresent(proposal: Proposal, author: User, actor: User) -> None:
    representation = _need(proposal.representation, "a representation")
    representation.annotations.remove(_need(proposal.annotation, "an annotation"))


def _undescribe(proposal: Proposal, author: User, actor: User) -> None:
    _need(proposal.metadata, "a metadata link").delete()
    proposal.metadata = None  # gone; ``values["link"]`` says what it was


APPLY: dict[str, Callable[[Proposal, User, User], None]] = {
    Kind.LINK: _link,
    Kind.NEW_ANNOTATION: _new_annotation,
    Kind.IGNORE: _ignore,
    Kind.UNASSIGN: _unassign,
    Kind.EDIT_ANNOTATION: _edit_annotation,
    Kind.NEW_REPRESENTATION: _representation,
    Kind.EDIT_REPRESENTATION: _representation,
    Kind.REPRESENT: _represent,
    Kind.DESCRIBE: _describe,
    Kind.UNREPRESENT: _unrepresent,
    Kind.UNDESCRIBE: _undescribe,
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
        return [row for row in rows if row[1] or row[2]]
    if kind in {Kind.EDIT_ANNOTATION, Kind.EDIT_REPRESENTATION, Kind.NEW_REPRESENTATION}:
        fields = (
            ("name", "description", "note")
            if kind == Kind.EDIT_ANNOTATION
            else REPRESENTATION_FIELDS
        )
        before = proposal.base
        rows = [
            (field.capitalize(), _shown(field, before.get(field)), _shown(field, values.get(field)))
            for field in fields
            if _shown(field, before.get(field)) != _shown(field, values.get(field))
        ]
        if values.get("relation"):
            rows.append(("Linked", "", f"{values['relation']} {proposal.annotation}"))
        rows += [("Metadata", "", _metadata_row(row)) for row in values.get("metadata") or []]
        return rows
    linked = f"{proposal.representation}"
    if kind == Kind.REPRESENT:
        return [("Entity of", "", linked)]
    if kind == Kind.DESCRIBE:
        return [("Describes", "", f"{linked}: {proposal.role} of the {proposal.subject}")]
    if kind == Kind.UNREPRESENT:
        return [("Entity of", linked, "none")]
    return [("Describes", values.get("link", ""), "none")]


def _metadata_row(row: dict[str, Any]) -> str:
    """``{"subject": "activity", "role": 3, "annotation": 7}`` in words: "Date: when of the
    activity"."""
    role = MetadataRole.objects.filter(pk=row.get("role") or 0).first()
    annotation = Annotation.objects.filter(pk=row.get("annotation") or 0).first()
    return f"{annotation or '(deleted)'}: {role or '(deleted)'} of the {row.get('subject', '')}"


def _assignment(base: dict[str, Any]) -> str:
    if base.get("ignored"):
        return "not a data point"
    if base.get("annotation"):
        found = Annotation.objects.filter(pk=base["annotation"]).first()
        return str(found) if found else "(deleted)"
    return "none"


def _shown(field: str, value: Any) -> str:  # noqa: ANN401
    """A form value in words (vocabulary terms by name)."""
    if value in (None, ""):
        return ""
    if field in SLOTS:
        model = ObjectType if field == "target" else VOCABULARIES[field]
        term = model.objects.filter(pk=value).first()
        return str(term) if term else str(value)
    return str(value)
