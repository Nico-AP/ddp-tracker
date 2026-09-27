"""The uploader's own values: a few real values per data point, for the uploader only.

They make annotating easier, and the uploader may add them to the public examples after checking
them (docs/docs/tracker/concepts.md, "The uploader's values"). They can hold personal data, so:

- the parse task collects them as ``ddp_parser`` samples, email addresses masked, and takes them
  out of the upload's document again (``split_values``);
- they are sealed with the upload's public key (``UploadValues``). The private key is only in a
  signed cookie in the uploader's browser: never in the session or the database, so a database
  dump alone reveals nothing;
- reading them needs the cookie, the uploader's login and an unexpired row (``own_values``).
  Logging out deletes the cookies, which leaves the values unreadable; expired rows are purged.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from nacl.encoding import Base64Encoder
from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, PublicKey, SealedBox

from ddp_parser import Options, mask
from ddp_tracker.ddps.models import Upload, UploadValues

COOKIE_PREFIX = "ddp_values_"
COOKIE_SALT = "ddp_tracker.ddps.values"
MASKED_SHAPES = ("email",)  # masked even for the uploader; the parser masks whole values
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")  # ... and this, addresses inside texts

type Value = str | int | float | bool
type Values = dict[str, list[Value]]


def parse_options() -> Options:
    return Options(
        samples=True, max_samples=settings.DDP_VALUES_PER_POINT, masked_shapes=MASKED_SHAPES
    )


def split_values(document: dict[str, Any]) -> Values:
    """Take the samples (and the number ranges, only there with samples) out of every node of a
    ``to_dict`` document, in place; return the samples by path.

    ``{"root": {"path": "/a.json", "samples": {"values": ["Hi anna@x.com"]}, …}}`` becomes
    ``{"root": {"path": "/a.json", …}}`` and returns ``{"/a.json": ["Hi axxx@x.xxx"]}``.
    """
    found: Values = {}
    pending = [document["root"]]
    while pending:
        node = pending.pop()
        samples = node.pop("samples", None)
        node.pop("range", None)
        if samples:
            found[node["path"]] = [_masked(value) for value in samples["values"]]
        pending.extend(node.get("children") or [])
        pending.extend((node.get("properties") or {}).values())
        if node.get("items"):
            pending.append(node["items"])
    return found


def _masked(value: Value) -> Value:
    if isinstance(value, str):
        return EMAIL.sub(lambda match: mask(match.group()), value)
    return value


def new_key_pair() -> tuple[str, str]:
    """A private and a public key, base64."""
    private = PrivateKey.generate()
    return (
        private.encode(Base64Encoder).decode(),
        private.public_key.encode(Base64Encoder).decode(),
    )


def keep(upload: Upload, values: Values, public_key: str) -> None:
    """Seal ``values`` with ``public_key`` and store them until the retention time is over."""
    box = SealedBox(PublicKey(public_key.encode(), Base64Encoder))
    UploadValues.objects.update_or_create(
        upload=upload,
        defaults={
            "sealed": box.encrypt(json.dumps(values).encode()),
            "expires_at": timezone.now() + timedelta(days=settings.DDP_VALUES_RETENTION_DAYS),
        },
    )


def cookie_name(upload: Upload) -> str:
    return f"{COOKIE_PREFIX}{upload.pk}"


def remember(response: HttpResponse, upload: Upload, private_key: str) -> None:
    """Give the uploader's browser the key to their values."""
    response.set_signed_cookie(
        cookie_name(upload),
        private_key,
        salt=COOKIE_SALT,
        max_age=settings.DDP_VALUES_RETENTION_DAYS * 24 * 60 * 60,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


@dataclass
class OwnValues:
    """What the uploader may see: their values, or only that they are unreadable here (the key
    is in another browser, or was deleted by logging out)."""

    values: Values = field(default_factory=dict)
    readable: bool = True
    expires_at: datetime | None = None


def own_values(request: HttpRequest, upload: Upload | None) -> OwnValues | None:
    """The uploader's values of ``upload``; ``None`` for anyone else, or when there are none."""
    if upload is None or not _is_uploader(request, upload):
        return None
    cache: dict[int, OwnValues | None] = request.__dict__.setdefault("_ddp_own_values", {})
    if upload.pk not in cache:
        cache[upload.pk] = _read(request, upload)
    return cache[upload.pk]


def _is_uploader(request: HttpRequest, upload: Upload) -> bool:
    user = request.user
    return bool(user.is_authenticated and upload.uploaded_by_id == user.pk)


def _read(request: HttpRequest, upload: Upload) -> OwnValues | None:
    row = UploadValues.objects.filter(upload=upload, expires_at__gt=timezone.now()).first()
    if row is None:
        return None
    key = request.get_signed_cookie(cookie_name(upload), default=None, salt=COOKIE_SALT)
    if key is None:  # missing, or a bad signature
        return OwnValues(readable=False, expires_at=row.expires_at)
    try:
        box = SealedBox(PrivateKey(key.encode(), Base64Encoder))
        values: Values = json.loads(box.decrypt(bytes(row.sealed)))
    except (CryptoError, ValueError):  # another upload's key, or a broken one
        return OwnValues(readable=False, expires_at=row.expires_at)
    return OwnValues(values, expires_at=row.expires_at)


def forget(response: HttpResponse, upload: Upload) -> None:
    """Delete the values of ``upload`` and their key."""
    UploadValues.objects.filter(upload=upload).delete()
    response.delete_cookie(cookie_name(upload), samesite="Lax")


def forget_keys(request: HttpRequest, response: HttpResponse) -> None:
    """Delete all keys this browser holds (on logout)."""
    for name in request.COOKIES:
        if name.startswith(COOKIE_PREFIX):
            response.delete_cookie(name, samesite="Lax")


def purge() -> int:
    """Delete the expired values; returns how many uploads' values were deleted."""
    deleted, _ = UploadValues.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
