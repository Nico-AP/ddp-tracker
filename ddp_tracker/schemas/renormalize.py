"""Applying a platform's current path rules to its stored uploads (``ddp_parser`` spec 3.6).

The raw DDPs are gone, but the schema documents keep every key, so a rule added later (e.g. "the
keys below ``ChatHistory`` are usernames") can still rename them. ``renormalize``:

1. applies the platform's rules, and the wrapper-folder check (spec 5), to each stored document
   (``ddp_parser.renormalize``) and saves the ones that changed;
2. re-registers the changed uploads that were registered: their observations are rebuilt, which
   creates the locations at the new paths (``services.register_upload``);
3. moves the curation of each renamed location that no upload observes any more to its new
   location (annotation, "not a data point", examples, representations, metadata links,
   suggestions), then deletes it. If both have an annotation, the new location's stays and the
   conflict is reported.

Renaming can't be undone: merged keys are gone from the documents, so removing a rule only
affects uploads parsed afterwards.
"""

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from ddp_parser import from_dict, to_dict
from ddp_parser import renormalize as renormalize_document
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.rules import options_for
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.representations.models import Representation, RepresentationMetadata
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.services import register_upload


@dataclass
class Report:
    uploads: int = 0  # uploads whose document changed
    paths: set[str] = field(default_factory=set)  # the new paths (old ones can be personal)
    moved: int = 0  # locations whose curation moved to a new location
    conflicts: list[str] = field(default_factory=list)


@transaction.atomic
def renormalize(platform: Platform, *, dry_run: bool = False) -> Report:
    """Apply ``platform``'s current rules to its stored uploads (see the module docstring).
    With ``dry_run``, only report which uploads and paths would change.
    """
    platform = Platform.objects.select_for_update().get(pk=platform.pk)
    options = options_for(platform)
    report = Report()
    renames: dict[str, str] = {}
    changed: list[Upload] = []
    for upload in platform.uploads.filter(document__isnull=False).order_by("requested_at", "pk"):
        assert upload.document is not None
        result = renormalize_document(from_dict(upload.document), options)
        if result.renames:
            renames |= result.renames
            upload.document = to_dict(result.document)
            changed.append(upload)
    report.uploads, report.paths = len(changed), set(renames.values())
    if dry_run or not changed:
        return report
    for upload in changed:
        upload.save(update_fields=["document"])
    registered = [upload for upload in changed if upload.registered_at is not None]
    Observation.objects.filter(upload__in=registered).delete()
    for upload in registered:
        upload.registered_at = None
        upload.save(update_fields=["registered_at"])
        register_upload(upload)
    _move_curation(platform, renames, report)
    return report


def _move_curation(platform: Platform, renames: dict[str, str], report: Report) -> None:
    paths = set(renames) | set(renames.values())
    locations = {location.path: location for location in platform.locations.filter(path__in=paths)}
    moved: dict[int, int] = {}  # old location → new location
    for old_path, new_path in renames.items():
        old, new = locations.get(old_path), locations.get(new_path)
        if old is None or new is None or old.observations.exists():
            continue  # still observed as it was: an upload the rules left unchanged
        _merge(old, new, report)
        moved[old.pk] = new.pk
    _remap_proposals(moved)
    Location.objects.filter(pk__in=moved).delete()
    report.moved = len(moved)


def _merge(old: Location, new: Location, report: Report) -> None:
    """Move ``old``'s curation to ``new``."""
    if old.annotation_id is not None:
        if new.annotation_id is None:
            new.annotation_id, new.ignored = old.annotation_id, False
        elif new.annotation_id != old.annotation_id:
            report.conflicts.append(
                f"{new.path}: kept the annotation “{new.annotation}”, "
                f"dropped “{old.annotation}” of a renamed location"
            )
    elif old.ignored and new.annotation_id is None:
        new.ignored = True
    new.example_values = new.example_values + [
        value for value in old.example_values if value not in new.example_values
    ]
    new.save(update_fields=["annotation", "ignored", "example_values"])
    Representation.objects.filter(location=old).update(location=new)
    for link in RepresentationMetadata.objects.filter(location=old):
        duplicate = RepresentationMetadata.objects.filter(
            representation=link.representation_id,
            location=new,
            role=link.role_id,
            subject=link.subject,
        )
        if duplicate.exists():
            link.delete()
        else:
            link.location = new
            link.save(update_fields=["location"])
    Proposal.objects.filter(location=old).update(location=new)


def _remap_proposals(moved: dict[int, int]) -> None:
    """Point the location ids inside suggestions (``values`` / ``base``: ``also``, metadata
    rows) at the new locations.
    """
    if not moved:
        return
    mentioning = Proposal.objects.filter(values__has_any_keys=["also", "metadata"]) | (
        Proposal.objects.filter(base__has_key="metadata")
    )
    for proposal in mentioning:
        before = (proposal.values, proposal.base)
        proposal.values, proposal.base = (
            _remapped(proposal.values, moved),
            _remapped(proposal.base, moved),
        )
        if (proposal.values, proposal.base) != before:
            proposal.save(update_fields=["values", "base"])


def _remapped(data: dict[str, Any], moved: dict[int, int]) -> dict[str, Any]:
    data = dict(data)
    if isinstance(data.get("also"), list):
        data["also"] = list(dict.fromkeys(moved.get(pk, pk) for pk in data["also"]))
    if isinstance(data.get("metadata"), list):
        data["metadata"] = [_remapped_row(row, moved) for row in data["metadata"]]
    return data


def _remapped_row(row: object, moved: dict[int, int]) -> object:
    if isinstance(row, dict) and isinstance(location := row.get("location"), int):
        return {**row, "location": moved.get(location, location)}
    return row
