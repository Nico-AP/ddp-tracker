"""Plausibility of uploads: whether a parsed upload may count towards the public schema.

After parsing (``tasks.parse_upload``), ``decide`` either registers the upload or holds it:

- the same file as an upload that counts or waits → **duplicate** (never counted twice);
- the first upload of its platform and file format → **awaiting** staff approval (it defines
  what the others are compared with);
- too unlike the other uploads of its platform and format → **unconfirmed**: the uploader
  confirms it (→ awaiting approval) or discards it;
- else → **passed**, registered.

Definitions: docs/tracker/concepts.md ("Upload checks").
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ddp_parser import from_dict
from ddp_tracker.ddps.inspection import inspect
from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.services import get_format_of, register_upload
from ddp_tracker.users.models import User

Plausibility = Upload.Plausibility
_WAITING = (Plausibility.PASSED, Plausibility.APPROVED, Plausibility.AWAITING)


def peers_of(upload: Upload) -> "list[Upload]":
    """The uploads ``upload`` is compared with: same platform and format, counted."""
    root_format = upload.root_format
    if not root_format and upload.document is not None:
        root_format = get_format_of(from_dict(upload.document).root)
    return list(
        Upload.objects.filter(
            platform=upload.platform_id,
            root_format=root_format,
            plausibility__in=(Plausibility.PASSED, Plausibility.APPROVED),
            document__isnull=False,
        )
        .exclude(pk=upload.pk)
        .only("document")
    )


def similarity(upload: Upload, peers: "list[Upload] | None" = None) -> float | None:
    """The share of ``upload``'s data points its peers already know: at the same path, or
    through a ``moved``/``renamed`` suggestion (so moved or translated exports still match).
    None without peers, or without data points to compare. The same figure the inspection
    explains (``inspection.py``).
    """
    if upload.document is None:
        return None
    return inspect(upload, peers or peers_of(upload)).share


@transaction.atomic
def decide(upload: Upload) -> None:
    """Register a freshly parsed upload, or hold it (see the module docstring)."""
    assert upload.document is not None
    upload.root_format = get_format_of(from_dict(upload.document).root)
    if upload.duplicates().filter(plausibility__in=_WAITING).exists():
        upload.plausibility = Plausibility.DUPLICATE
    elif not (peers := peers_of(upload)):
        upload.plausibility = Plausibility.AWAITING
        upload.plausibility_reason = Upload.Reason.FIRST
    else:
        upload.similarity = similarity(upload, peers)
        # no data points at all (e.g. only unreadable files) is as unusual as a low share
        if upload.similarity is None or upload.similarity < settings.DDP_SIMILARITY_THRESHOLD:
            upload.plausibility = Plausibility.UNCONFIRMED
            upload.plausibility_reason = Upload.Reason.DISSIMILAR
        else:
            upload.plausibility = Plausibility.PASSED
    upload.save(update_fields=["root_format", "plausibility", "plausibility_reason", "similarity"])
    if upload.plausibility == Plausibility.PASSED:
        register_upload(upload)


# --- what people do with a held upload ---------------------------------------------------------


class NotAllowedError(Exception):
    """The action doesn't apply to this upload, or not for this user."""


def confirm(upload: Upload, user: User) -> None:
    """The uploader says an unusual upload is right: it waits for staff approval."""
    if upload.plausibility != Plausibility.UNCONFIRMED or upload.uploaded_by_id != user.pk:
        raise NotAllowedError
    upload.plausibility = Plausibility.AWAITING
    upload.save(update_fields=["plausibility"])


def discard(upload: Upload, user: User) -> None:
    """The uploader withdraws an unusual upload: it is deleted, with its schema document."""
    if upload.plausibility != Plausibility.UNCONFIRMED or upload.uploaded_by_id != user.pk:
        raise NotAllowedError
    upload.delete()


def can_inspect(upload: Upload, user: User) -> bool:
    """The uploader and staff look into an upload that isn't registered (a registered one has
    its review). It may not be a DDP at all, so nobody else sees its names and keys."""
    if upload.document is None or upload.registered_at is not None:
        return False
    return user.is_staff or upload.uploaded_by_id == user.pk


def can_approve(upload: Upload, user: User) -> bool:
    """Staff decide on waiting uploads (their own included)."""
    return upload.plausibility == Plausibility.AWAITING and user.is_staff


@transaction.atomic
def approve(upload: Upload, user: User) -> None:
    if not can_approve(upload, user):
        raise NotAllowedError
    upload.plausibility = Plausibility.APPROVED
    upload.approved_by, upload.approved_at = user, timezone.now()
    upload.save(update_fields=["plausibility", "approved_by", "approved_at"])
    register_upload(upload)


def reject(upload: Upload, user: User) -> None:
    if not can_approve(upload, user):
        raise NotAllowedError
    upload.plausibility = Plausibility.REJECTED
    upload.approved_by, upload.approved_at = user, timezone.now()
    upload.save(update_fields=["plausibility", "approved_by", "approved_at"])
