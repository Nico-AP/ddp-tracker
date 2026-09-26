"""Linking annotations to representations, and suggesting vocabulary terms."""

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.representations.models import (
    MetadataRole,
    Representation,
    RepresentationMetadata,
    Vocabulary,
)
from ddp_tracker.users.models import User


def represent(representation: Representation, annotation: Annotation) -> None:
    """``annotation`` is (one platform's node of) ``representation`` itself."""
    representation.annotations.add(annotation)


def describe(
    representation: Representation,
    annotation: Annotation,
    role: MetadataRole,
    subject: str,
) -> RepresentationMetadata:
    """Link ``annotation`` as ``role`` of ``subject``, validated (``.add()`` would skip that)."""
    link = RepresentationMetadata(
        representation=representation, annotation=annotation, role=role, subject=subject
    )
    link.full_clean()
    link.save()
    return link


def suggest_term[T: Vocabulary](model: type[T], name: str, description: str, user: User) -> T:
    """A new term, pending until an admin approves it."""
    return model.objects.create(name=name, description=description, created_by=user)
