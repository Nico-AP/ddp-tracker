"""Turn an empty database into a demo (``manage.py seed_demo``): the rows of ``spec.py``, made
through the same code as the site uses (the parse task, the plausibility checks, the curating
services), so the demo is what real uploads and real curation would give.

Everything is looked up before it is created: seeding twice creates nothing twice, and what a
person changed in between stays as it is.
"""

import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet

from allauth.account.models import EmailAddress

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps import checks
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.names import anonymize_file_name
from ddp_tracker.ddps.tasks import parse_upload
from ddp_tracker.journeys.demo.ddps import build_zip
from ddp_tracker.journeys.demo.spec import (
    ADMIN,
    ADMIN_EMAIL,
    ANNOTATIONS,
    CURATOR,
    CURATOR_EMAIL,
    EXAMPLES,
    PLATFORMS,
    REPRESENTATIONS,
    SUGGESTED_TERM,
    SUGGESTION_COMMENT,
    SUGGESTION_PATH,
    SUGGESTION_VALUES,
    UPLOADS,
    UploadSpec,
)
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import submit
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
)
from ddp_tracker.representations.services import describe, suggest_term
from ddp_tracker.schemas.examples import USER_INPUT, add_examples
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation, link
from ddp_tracker.users.models import User


class SeedError(Exception):
    """The demo data can't be made as specified; the message says what is wrong."""


@transaction.atomic
def seed(password: str) -> Counter[str]:
    """Create what is missing of the demo data; returns how much of each kind was created.
    ``password`` is set on the demo users that are created (existing ones keep theirs)."""
    created: Counter[str] = Counter()
    users = {
        ADMIN: _user(ADMIN_EMAIL, "Demo admin", password, created, staff=True),
        CURATOR: _user(CURATOR_EMAIL, "Demo curator", password, created, staff=False),
    }
    platforms = {slug: _platform(slug, name, created) for slug, name in PLATFORMS}
    for spec in UPLOADS:
        _upload(spec, platforms[spec.platform], users[spec.uploader], users[ADMIN], created)
    _annotations(platforms, users[ADMIN], created)
    _representations(platforms, users[ADMIN], created)
    _examples(platforms, created)
    _suggestions(platforms, users[CURATOR], created)
    return created


# --- users, platforms, uploads ----------------------------------------------------------------


def _user(email: str, name: str, password: str, created: Counter[str], *, staff: bool) -> User:
    user = User.objects.filter(email=email).first()
    if user is None:
        make = User.objects.create_superuser if staff else User.objects.create_user
        user = make(email, password, name=name)
        created["users"] += 1
    # accounts sign in with a verified e-mail address
    EmailAddress.objects.get_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _platform(slug: str, name: str, created: Counter[str]) -> Platform:
    platform, is_new = Platform.objects.get_or_create(slug=slug, defaults={"name": name})
    created["platforms"] += is_new
    return platform


def _upload(
    spec: UploadSpec, platform: Platform, uploader: User, admin: User, created: Counter[str]
) -> None:
    """One fictional package, as if uploaded through the form: parsed by the real task (which
    deletes the file), checked, and approved by the demo admin unless it is to stay held."""
    same = Upload.objects.filter(
        platform=platform, requested_at=spec.requested_at, uploaded_by=uploader
    )
    if same.exists():
        return
    upload = Upload.objects.create(
        platform=platform,
        requested_at=spec.requested_at,
        language="en",
        request_mode=Upload.RequestMode.DL_BROWSER,
        request_format=Upload.RequestFormat.JSON,
        file_format=Upload.FileFormat.ZIP,
        file_name=anonymize_file_name(spec.file_name),
        uploaded_by=uploader,
    )
    incoming = Path(settings.DDP_INCOMING_DIR)
    incoming.mkdir(parents=True, exist_ok=True)
    path = incoming / f"{upload.pk}-{uuid.uuid4().hex}"
    path.write_bytes(build_zip(spec.build()))
    parse_upload.call(upload.pk, str(path))  # now, whatever the task backend is
    upload.refresh_from_db()
    if upload.status != Upload.Status.DONE:
        msg = f"{spec.file_name} could not be parsed: {upload.error}"
        raise SeedError(msg)
    created["uploads"] += 1
    if spec.hold:
        return
    if upload.plausibility == Upload.Plausibility.UNCONFIRMED:
        checks.confirm(upload, uploader)
    if upload.plausibility == Upload.Plausibility.AWAITING:
        checks.approve(upload, admin)
    upload.refresh_from_db()
    if upload.registered_at is None:
        msg = f"{spec.file_name} was not registered: it is {upload.get_plausibility_display()}."
        raise SeedError(msg)


# --- curation ---------------------------------------------------------------------------------


def _location(platform: Platform, path: str) -> Location:
    location = Location.objects.filter(platform=platform, path=path).first()
    if location is None:
        msg = (
            f"{platform} has no {path}: the parser or the fictional packages changed, "
            "so demo/spec.py needs updating."
        )
        raise SeedError(msg)
    return location


def _annotations(platforms: dict[str, Platform], admin: User, created: Counter[str]) -> None:
    for spec in ANNOTATIONS:
        platform = platforms[spec.platform]
        locations = [_location(platform, path) for path in spec.paths]
        annotation = Annotation.objects.filter(platform=platform, name=spec.name).first()
        if annotation is None:
            if locations[0].annotation_id is not None or locations[0].ignored:
                continue  # someone decided otherwise since (renamed it, say): leave it
            annotation = create_annotation(
                locations[0],
                spec.name,
                admin,
                description=spec.description,
                note=spec.note,
                pii=spec.pii,
            )
            created["annotations"] += 1
        for location in locations:  # the same data point at another path (moved, renamed)
            if location.annotation_id is None and not location.ignored:
                link(location, annotation)


def _representations(platforms: dict[str, Platform], admin: User, created: Counter[str]) -> None:
    for spec in REPRESENTATIONS:
        item = _location(platforms[spec.platform], spec.path)
        if item.representations.filter(name=spec.name).exists():
            continue
        representation = Representation(
            location=item,
            pattern=Pattern.ACTIVITY,
            name=spec.name,
            note=spec.note,
            actor=ActorType.objects.get(slug=spec.actor),
            activity=ActivityType.objects.get(slug=spec.activity),
            object=ObjectType.objects.get(slug=spec.object_type),
            updated_by=admin,
        )
        representation.full_clean()
        representation.save()
        for metadata in spec.metadata:
            describe(
                representation,
                _location(item.platform, f"{item.path}/{metadata.path}"),
                MetadataRole.objects.get(slug=metadata.role),
                metadata.subject,
            )
        created["representations"] += 1


def _examples(platforms: dict[str, Platform], created: Counter[str]) -> None:
    for spec in EXAMPLES:
        location = _location(platforms[spec.platform], spec.path)
        before = len(location.example_values)
        add_examples(location, list(spec.examples), USER_INPUT)
        created["example values"] += len(location.example_values) - before


def _suggestions(platforms: dict[str, Platform], curator: User, created: Counter[str]) -> None:
    """What a signed-in user who is not staff leaves for staff to decide: a vocabulary term and
    a suggested annotation."""
    name, description = SUGGESTED_TERM
    if not ActivityType.objects.filter(name=name).exists():
        suggest_term(ActivityType, name, description, curator)
        created["suggested terms"] += 1
    location = _location(platforms["tiktok"], SUGGESTION_PATH)
    if location.annotation_id is None and not Proposal.objects.filter(location=location).exists():
        submit(
            curator,
            Proposal.Kind.NEW_ANNOTATION,
            location=location,
            values=dict(SUGGESTION_VALUES),
            comment=SUGGESTION_COMMENT,
        )
        created["suggestions"] += 1


# --- reset ------------------------------------------------------------------------------------


@transaction.atomic
def reset() -> Counter[str]:
    """Remove what ``seed`` created; returns how much of each kind was removed. A demo platform
    that has uploads of other people stays, with what is known about it."""
    removed: Counter[str] = Counter()
    users = User.objects.filter(email__in=(ADMIN_EMAIL, CURATOR_EMAIL))
    removed["suggestions"] = _delete(Proposal.objects.filter(proposed_by__in=users))
    removed["suggested terms"] = _delete(
        ActivityType.objects.filter(created_by__in=users, representations__isnull=True)
    )
    removed["representations"] = _delete(Representation.objects.filter(updated_by__in=users))
    removed["annotations"] = _delete(Annotation.objects.filter(updated_by__in=users))
    removed["uploads"] = _delete(Upload.objects.filter(uploaded_by__in=users))
    for slug, _ in PLATFORMS:
        platform = Platform.objects.filter(slug=slug).first()
        if platform is not None and not platform.uploads.exists():
            platform.delete()  # with its locations
            removed["platforms"] += 1
    removed["users"] = _delete(users)
    return removed


def _delete(rows: QuerySet[Any]) -> int:
    """Delete ``rows``; how many of them there were (not counting what went with them)."""
    count = rows.count()
    rows.delete()
    return count
