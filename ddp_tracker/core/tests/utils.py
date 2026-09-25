"""Helpers for tests: real DDP zips and parsed uploads, so tests exercise the actual parser."""

import io
import zipfile
from datetime import date

from ddp_parser import parse, to_dict
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.schemas.services import register_upload
from ddp_tracker.users.models import User


def make_zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def parsed_upload(
    platform: Platform,
    members: dict[str, bytes],
    *,
    language: str = "",
    requested_at: date = date(2026, 9, 1),
    user: User | None = None,
    register: bool = False,
) -> Upload:
    """An upload in state ``done`` whose document is the parsed zip of ``members``; with
    ``register``, also added to the platform's collected schema.
    """
    return _upload(
        platform,
        make_zip(members),
        "export.zip",
        language=language,
        requested_at=requested_at,
        user=user,
        register=register,
    )


def parsed_file(platform: Platform, name: str, data: bytes, *, register: bool = False) -> Upload:
    """Like ``parsed_upload``, for a DDP that is a single file (e.g. ``posts.csv``)."""
    return _upload(platform, data, name, register=register)


def _upload(
    platform: Platform,
    data: bytes,
    name: str,
    *,
    language: str = "",
    requested_at: date = date(2026, 9, 1),
    user: User | None = None,
    register: bool = False,
) -> Upload:
    document = parse(data, name=name)
    upload = Upload.objects.create(
        platform=platform,
        requested_at=requested_at,
        language=language,
        file_name=name,
        uploaded_by=user,
        status=Upload.Status.DONE,
        document=to_dict(document),
        source_sha256=document.source.sha256,
        size_bytes=document.source.size_bytes,
    )
    if register:
        register_upload(upload)
    return upload
