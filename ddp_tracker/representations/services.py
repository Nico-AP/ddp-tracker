"""Describing representations with locations, and suggesting vocabulary terms."""

from ddp_tracker.representations.models import (
    MetadataRole,
    Representation,
    RepresentationMetadata,
    Vocabulary,
)
from ddp_tracker.schemas.models import Location
from ddp_tracker.users.models import User


def describe(
    representation: Representation,
    location: Location,
    role: MetadataRole,
    subject: str,
) -> RepresentationMetadata:
    """Link ``location`` as ``role`` of ``subject``, validated (``.create()`` would skip that)."""
    link = RepresentationMetadata(
        representation=representation, location=location, role=role, subject=subject
    )
    link.full_clean()
    link.save()
    return link


def suggest_term[T: Vocabulary](model: type[T], name: str, description: str, user: User) -> T:
    """A new term, pending until an admin approves it."""
    return model.objects.create(name=name, description=description, created_by=user)
