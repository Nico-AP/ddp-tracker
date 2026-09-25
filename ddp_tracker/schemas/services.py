"""The collected schema: registering uploads, reviewing them, triaging their data points."""

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

import msgspec

from ddp_parser import children, from_dict, is_data_point, merge_trees, suggest
from ddp_parser.model import Node
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles
from ddp_tracker.schemas.timeline import changes_in, new_in
from ddp_tracker.users.models import User

# Fields shown as the node's headline; everything else goes into ``details``.
_HEADLINE = {"name", "path", "kind", "type", "shape", "format", "children", "properties", "items"}
_BATCH = 500


def type_label(node: Node) -> str:
    """``string``, or a union like ``null|string``; empty for filesystem-only nodes."""
    value = getattr(node, "type", None)
    if value is None:
        return ""
    return "|".join(value) if isinstance(value, tuple) else str(value)


def node_details(node: Node) -> dict[str, Any]:
    """Everything about a node except its headline fields and subtree, as JSON data."""
    fields = {k: v for k, v in msgspec.structs.asdict(node).items() if k not in _HEADLINE}
    data: dict[str, Any] = msgspec.to_builtins(
        {k: v for k, v in fields.items() if v not in (None, {}, ())}
    )
    return data


@dataclass(frozen=True, slots=True)
class FlatNode:
    node: Node
    parent_path: str | None
    position: int


def flatten(root: Node) -> Iterator[FlatNode]:
    """Every node with its parent's path and its position among its siblings."""
    yield FlatNode(root, None, 0)
    stack = [root]
    while stack:
        parent = stack.pop()
        below = children(parent)
        for position, child in enumerate(below):
            yield FlatNode(child, parent.path, position)
        stack.extend(reversed(below))


# --- registering ------------------------------------------------------------------------------


def _root_format(root: Node) -> str:
    """ "zip" for an archive, else the single file's extension ("csv", "json" …)."""
    ext = getattr(root, "ext", None) or ""
    return ext.lstrip(".").lower() or root.kind


@transaction.atomic
def register_upload(upload: Upload) -> None:
    """Add a parsed upload to its platform's collected schema: a ``Location`` per new path (tree
    structure only) and an ``Observation`` per node. Then suggestions for its unknown data points,
    and fresh ones for the uploads requested later, whose earlier uploads now include this one.
    Registration order doesn't matter: everything is derived from observations and request dates.
    """
    if upload.registered_at is not None or upload.document is None:
        return
    platform = Platform.objects.select_for_update().get(pk=upload.platform_id)
    root = from_dict(upload.document).root
    existing = set(platform.locations.values_list("path", flat=True))
    flat = list(flatten(root))
    Location.objects.bulk_create(
        (
            Location(
                platform=platform,
                path=item.node.path,
                parent_path=item.parent_path,
                position=item.position,
                # the root's name is the uploaded file's name: per upload, possibly personal
                name=item.node.name if item.parent_path is not None else None,
            )
            for item in flat
            if item.node.path not in existing
        ),
        batch_size=_BATCH,
    )
    by_path = {location.path: location for location in platform.locations.all()}
    Observation.objects.bulk_create(
        (
            Observation(
                upload=upload,
                location=by_path[item.node.path],
                kind=item.node.kind,
                is_data_point=is_data_point(item.node),
                type=type_label(item.node),
                shape=getattr(item.node, "shape", None) or "",
                format=getattr(item.node, "format", None) or "",
                details=node_details(item.node),
            )
            for item in flat
        ),
        batch_size=_BATCH,
    )
    upload.root_format = _root_format(root)
    upload.registered_at = timezone.now()
    upload.save(update_fields=["root_format", "registered_at"])
    suggest_for(upload)
    for later in _registered(platform).filter(requested_at__gt=upload.requested_at):
        suggest_for(later)


def _registered(platform: Platform) -> QuerySet[Upload]:
    return platform.uploads.filter(registered_at__isnull=False, document__isnull=False)


def _reference(upload: Upload) -> Node | None:
    """What was known before ``upload``: the merged schemas of its platform's uploads requested
    strictly earlier (the same cut-off as "new"), or None if there are none.
    """
    earlier = _registered(upload.platform).filter(requested_at__lt=upload.requested_at)
    roots = [from_dict(u.document).root for u in earlier.only("document") if u.document is not None]
    return merge_trees(roots) if roots else None


def suggest_for(upload: Upload) -> None:
    """(Re)compute the suggestions of ``upload``'s unknown data points against ``_reference``."""
    if upload.document is None:
        return
    known = _reference(upload)
    root = from_dict(upload.document).root
    found = suggest(known, root) if known is not None else {}
    observations = list(upload.observations.select_related("location"))
    for observation in observations:
        observation.suggestions = [asdict(c) for c in found.get(observation.location.path, [])]
    Observation.objects.bulk_update(observations, ["suggestions"], batch_size=_BATCH)


# --- reviewing --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Choice:
    annotation: Annotation
    reason: str  # "moved" / "renamed"
    score: float
    via: str  # the known path it was found through


@dataclass(frozen=True)
class TriageItem:
    observation: Observation
    choices: list[Choice]
    is_new: bool  # no earlier-requested upload has the path

    @property
    def location(self) -> Location:
        return self.observation.location


@dataclass(frozen=True)
class Change:
    observation: Observation
    fields: list[str]  # kind / type / shape / format with a value no earlier upload had


@dataclass(frozen=True)
class Missing:
    location: Location
    profile: Profile  # over all uploads: how often and until when it was seen


@dataclass(frozen=True)
class Review:
    triage: list[TriageItem]  # untriaged data points of this upload, grouped by parent
    changed: list[Change]
    missing: list[Missing]  # locations of annotations this upload has nowhere


def choices(observation: Observation) -> list[Choice]:
    """The suggested annotations of a new data point: its candidates' annotations, best first."""
    paths = [s["path"] for s in observation.suggestions]
    linked = {
        location.path: location.annotation
        for location in Location.objects.filter(
            platform_id=observation.location.platform_id, path__in=paths, annotation__isnull=False
        ).select_related("annotation")
    }
    found: dict[int, Choice] = {}
    for candidate in observation.suggestions:
        annotation = linked.get(candidate["path"])
        if annotation is not None and annotation.pk not in found:
            found[annotation.pk] = Choice(
                annotation, candidate["reason"], candidate["score"], candidate["path"]
            )
    return list(found.values())


def review(upload: Upload) -> Review:
    """What a curator needs to look at for ``upload`` (definitions: docs/tracker/concepts.md)."""
    observations = upload.observations.select_related("location", "location__annotation")
    new = new_in(upload)
    untriaged = observations.filter(
        is_data_point=True, location__annotation__isnull=True, location__ignored=False
    ).order_by("location__parent_path", "location__position")
    changes = changes_in(upload)
    missing = list(
        upload.platform.locations.filter(annotation__isnull=False)
        .exclude(annotation__locations__observations__upload=upload)
        .select_related("annotation")
        .order_by("path")
    )
    seen = profiles(
        (location.pk for location in missing),
        Observation.objects.filter(upload__registered_at__isnull=False),
    )
    return Review(
        triage=[TriageItem(o, choices(o), o.location_id in new) for o in untriaged],
        changed=[
            Change(o, changes[o.location_id])
            for o in observations.filter(location_id__in=changes).order_by("location__path")
        ],
        missing=[Missing(location, seen[location.pk]) for location in missing],
    )


# --- triaging ---------------------------------------------------------------------------------


def link(location: Location, annotation: Annotation | None) -> None:
    """Attach ``location`` to ``annotation`` (or detach it with ``None``)."""
    location.annotation = annotation
    location.ignored = False
    location.save(update_fields=["annotation", "ignored"])


def ignore(location: Location) -> None:
    location.annotation = None
    location.ignored = True
    location.save(update_fields=["annotation", "ignored"])


def create_annotation(location: Location, name: str, user: User | None) -> Annotation:
    """A new annotation for ``location``, named ``name`` (made unique on the platform)."""
    annotation = _unique_annotation(location.platform, name, user)
    link(location, annotation)
    return annotation


def _unique_annotation(platform: Platform, name: str, user: User | None) -> Annotation:
    base = name.strip() or "unnamed"
    for attempt in range(1, 1000):
        candidate = base if attempt == 1 else f"{base} ({attempt})"
        try:
            with transaction.atomic():
                return Annotation.objects.create(platform=platform, name=candidate, updated_by=user)
        except IntegrityError:
            continue
    msg = f"no free annotation name for {base!r}"  # pragma: no cover
    raise RuntimeError(msg)  # pragma: no cover


def accept_suggestions(upload: Upload) -> int:
    """Link every untriaged data point of ``upload`` to its best suggested annotation."""
    linked = 0
    for item in review(upload).triage:
        if item.choices:
            link(item.location, item.choices[0].annotation)
            linked += 1
    return linked


def create_remaining(upload: Upload, user: User | None, parent_path: str | None = None) -> int:
    """A new annotation (named after the key) for every untriaged data point left in ``upload``, or only
    below ``parent_path``.
    """
    created = 0
    for item in review(upload).triage:
        location = item.location
        if parent_path is not None and location.parent_path != parent_path:
            continue
        create_annotation(location, location.default_name, user)
        created += 1
    return created
