"""The collected schema: registering uploads, reviewing them, triaging their data points."""

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

import msgspec

from ddp_parser import Candidate, children, from_dict, is_data_point, merge_trees, suggest, walk
from ddp_parser.model import FilesystemNode, Node
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles
from ddp_tracker.schemas.timeline import FieldChange, change_details, new_in
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


def get_format_of(root: Node) -> str:
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
    upload.root_format = get_format_of(root)
    upload.registered_at = timezone.now()
    upload.save(update_fields=["root_format", "registered_at"])
    suggest_for(upload)
    for later in _registered(platform).filter(requested_at__gt=upload.requested_at):
        suggest_for(later)


def _registered(platform: Platform) -> QuerySet[Upload]:
    return platform.uploads.filter(registered_at__isnull=False, document__isnull=False)


def _references(upload: Upload) -> list[Node]:
    """What was known before ``upload``: the merged schemas of its platform's uploads requested
    strictly earlier (the same cut-off as "new"), one tree per root format. A single-file export
    and a zip don't share a root, so merging them would drop one of them.
    """
    earlier = _registered(upload.platform).filter(requested_at__lt=upload.requested_at)
    by_format: dict[str, list[FilesystemNode]] = {}
    for other in earlier.only("document", "root_format"):
        if other.document is not None:
            by_format.setdefault(other.root_format, []).append(from_dict(other.document).root)
    return [merge_trees(roots) for roots in by_format.values()]


def suggest_for(upload: Upload) -> None:
    """(Re)compute the suggestions of ``upload``'s unknown data points against its references:
    candidates from every root format, best first; none for a path any of them knows.
    """
    if upload.document is None:
        return
    root = from_dict(upload.document).root
    references = _references(upload)
    known = {node.path for reference in references for node in walk(reference)}
    found: dict[str, dict[str, Candidate]] = {}
    for reference in references:
        for path, candidates in suggest(reference, root).items():
            if path in known:
                continue
            best = found.setdefault(path, {})
            for candidate in candidates:  # the same known path from two formats: the best score
                if candidate.path not in best or candidate.score > best[candidate.path].score:
                    best[candidate.path] = candidate
    observations = list(upload.observations.select_related("location"))
    for observation in observations:
        candidates = sorted(
            found.get(observation.location.path, {}).values(), key=lambda c: -c.score
        )
        observation.suggestions = [asdict(c) for c in candidates]
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

    @property
    def candidate(self) -> dict[str, Any] | None:
        """The best suggestion ``{path, reason, score}``, annotated or not."""
        suggestions = self.observation.suggestions
        return suggestions[0] if suggestions else None

    @property
    def status(self) -> str:
        """``moved`` / ``renamed`` (a suggestion), ``new`` (no earlier upload has the path) or
        ``seen`` (earlier uploads had it, but it was never annotated)."""
        if self.candidate is not None:
            return str(self.candidate["reason"])
        return "new" if self.is_new else "seen"

    @property
    def within_group(self) -> str:
        """The path below its list (``<item>/date``), for rows grouped under the list."""
        rest = self.location.path[len(self.group) :].lstrip("/")
        return "/".join("<item>" if part == "[]" else part for part in rest.split("/"))

    @property
    def block(self) -> str:
        """Rows that belong together (a list and its items' fields share one stripe): the list's
        path for a list and everything inside its items, else the row's own path."""
        return self.group or self.location.path

    @property
    def group(self) -> str:
        """For data points inside a list's items: the list's path (their rows are grouped under
        it); "" for everything else."""
        path = self.location.path
        return path.rsplit(ITEM, 1)[0] if ITEM + "/" in path or path.endswith(ITEM) else ""


@dataclass(frozen=True)
class ChangedItem:
    observation: Observation
    diffs: list[FieldChange]  # each field with a value no earlier upload had, and what they had

    @property
    def fields(self) -> list[str]:
        return [diff.field for diff in self.diffs]


@dataclass(frozen=True)
class MissingItem:
    location: Location
    profile: Profile  # over all uploads: how often and until when it was seen


@dataclass(frozen=True)
class Review:
    triage: list[TriageItem]  # untriaged data points of this upload, grouped by parent
    changed: list[ChangedItem]
    missing: list[MissingItem]  # locations of annotations this upload has nowhere (unless moved)


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


def _in_file_order(found: list[Observation]) -> list[Observation]:
    """Depth first, siblings in file order (as the explorer's tree shows them)."""
    if not found:
        return found
    ancestors: set[str] = set()
    for observation in found:
        parts = observation.location.path.split("/")
        ancestors.update("/".join(parts[:end]) for end in range(2, len(parts) + 1))
    positions = dict(
        Location.objects.filter(
            platform=found[0].location.platform_id, path__in=ancestors
        ).values_list("path", "position")
    )

    def key(observation: Observation) -> tuple[tuple[int, str], ...]:
        parts = observation.location.path.split("/")
        prefixes = ["/".join(parts[:end]) for end in range(2, len(parts) + 1)]
        return tuple((positions.get(prefix, 0), prefix) for prefix in prefixes)

    return sorted(found, key=key)


def review(upload: Upload) -> Review:
    """What a curator needs to look at for ``upload`` (definitions: docs/tracker/concepts.md)."""
    observations = upload.observations.select_related("location", "location__annotation")
    new = new_in(upload)
    untriaged = _in_file_order(
        list(
            observations.filter(
                is_data_point=True, location__annotation__isnull=True, location__ignored=False
            )
        )
    )
    changes = change_details(upload)
    present = set(upload.observations.values_list("location__path", flat=True))
    # an annotated path that a data point here likely matches (at another path or under another
    # key name) isn't missing: it appears once, as that data point's "likely matches …"
    moved_from = {o.suggestions[0]["path"] for o in untriaged if o.suggestions}
    missing = [
        location
        for location in upload.platform.locations.filter(annotation__isnull=False)
        .exclude(annotation__locations__observations__upload=upload)
        .select_related("annotation")
        .order_by("path")
        # a list's item is absent when the list is empty: not missing, just no items this time
        if not (location.path.endswith(ITEM) and location.parent_path in present)
        and location.path not in moved_from
    ]
    seen = profiles(
        (location.pk for location in missing),
        Observation.objects.filter(upload__registered_at__isnull=False),
    )
    return Review(
        triage=[TriageItem(o, choices(o), o.location_id in new) for o in untriaged],
        changed=[
            ChangedItem(o, changes[o.location_id])
            for o in observations.filter(location_id__in=changes).order_by("location__path")
        ],
        missing=[MissingItem(location, seen[location.pk]) for location in missing],
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


def create_with_list(item: Location, name: str, user: User | None) -> Annotation:
    """A new annotation for a list's item (e.g. "ID"), and the suggested one for its list ("List
    of ID") if the list has none yet.
    """
    annotation = create_annotation(item, name, user)
    parent = Location.objects.filter(
        platform=item.platform_id, path=item.parent_path, annotation__isnull=True, ignored=False
    ).first()
    if parent is not None:
        create_annotation(parent, list_name(annotation.name), user)
    return annotation


def list_name(item_name: str) -> str:
    """The suggested name for a list whose item is annotated as ``item_name``."""
    return f"List of {item_name}"
