"""One-off data migration: redact paths in stored documents and schema locations."""

# ruff: noqa: ANN001

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db import transaction

from ddp_parser import redact_document_paths, redact_path
from ddp_parser.model.paths import split


def redact_stored_paths(apps, schema_editor) -> None:
    Upload = apps.get_model("ddps", "Upload")
    Location = apps.get_model("schemas", "Location")

    for upload in Upload.objects.exclude(document__isnull=True).iterator():
        document: dict[str, Any] = upload.document
        redact_document_paths(document)
        upload.document = document
        upload.save(update_fields=["document"])

    platform_ids = Location.objects.values_list("platform_id", flat=True).distinct()
    for platform_id in platform_ids:
        _migrate_platform(apps, platform_id)


def _migrate_platform(apps, platform_id: int) -> None:
    Location = apps.get_model("schemas", "Location")
    Observation = apps.get_model("schemas", "Observation")

    locations = list(Location.objects.filter(platform_id=platform_id).order_by("pk"))
    mapping = {location.path: redact_path(location.path) for location in locations}

    by_target: defaultdict[str, list[Any]] = defaultdict(list)
    for location in locations:
        by_target[mapping[location.path]].append(location)

    with transaction.atomic():
        for group in by_target.values():
            if len(group) > 1:
                _merge_locations(apps, group)

        for location in Location.objects.filter(platform_id=platform_id):
            old_path = location.path
            new_path = mapping[old_path]
            if old_path == new_path:
                continue
            old_parent = location.parent_path
            new_parent = (
                redact_path(old_parent)
                if old_parent is not None and old_parent != ""
                else old_parent
            )
            location.path = new_path
            location.parent_path = new_parent
            location.name = _migrated_name(location, old_path, new_path)
            location.save(update_fields=["path", "parent_path", "name"])

        for observation in Observation.objects.filter(location__platform_id=platform_id):
            suggestions = [_redact_suggestion(entry) for entry in observation.suggestions]
            if suggestions != observation.suggestions:
                observation.suggestions = suggestions
                observation.save(update_fields=["suggestions"])


def _migrated_name(location, old_path: str, new_path: str) -> str | None:
    if location.name is None:
        return None
    old_parts = split(old_path) if old_path else []
    new_parts = split(new_path) if new_path else []
    if new_parts and new_parts[-1] == "{*}":
        return location.name
    if old_parts and location.name == old_parts[-1] and new_parts:
        return new_parts[-1]
    return location.name


def _redact_suggestion(entry: dict[str, Any]) -> dict[str, Any]:
    if "path" not in entry:
        return entry
    updated = dict(entry)
    updated["path"] = redact_path(entry["path"])
    return updated


def _merge_locations(apps, group: list[Any]) -> None:
    """Keep the lowest pk; re-point related rows from the rest."""
    group.sort(key=lambda location: location.pk)
    keep, *remove = group
    Observation = apps.get_model("schemas", "Observation")
    Proposal = apps.get_model("proposals", "Proposal")
    Representation = apps.get_model("representations", "Representation")
    MetadataLink = apps.get_model("representations", "MetadataLink")

    for duplicate in remove:
        for observation in Observation.objects.filter(location=duplicate):
            conflict = Observation.objects.filter(upload=observation.upload, location=keep).first()
            if conflict:
                observation.delete()
            else:
                observation.location = keep
                observation.save(update_fields=["location"])

        Proposal.objects.filter(location=duplicate).update(location=keep)
        Representation.objects.filter(location=duplicate).update(location=keep)
        MetadataLink.objects.filter(location=duplicate).update(location=keep)

        if duplicate.annotation_id and not keep.annotation_id:
            keep.annotation_id = duplicate.annotation_id
            keep.save(update_fields=["annotation_id"])

        duplicate.delete()
