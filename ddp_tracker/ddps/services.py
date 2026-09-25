"""Receiving uploads: park the file privately, then hand it to the parse task."""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.tasks import parse_upload


def receive(upload: Upload, file: UploadedFile) -> None:
    """Store ``file`` in the private incoming directory and enqueue its parsing once ``upload``
    is committed. The task deletes the file after reading it.
    """
    incoming = Path(settings.DDP_INCOMING_DIR)
    incoming.mkdir(parents=True, exist_ok=True)
    path = incoming / f"{upload.pk}-{uuid.uuid4().hex}"
    with path.open("wb") as target:
        for chunk in file.chunks():
            target.write(chunk)
    transaction.on_commit(lambda: parse_upload.enqueue(upload.pk, str(path)))
