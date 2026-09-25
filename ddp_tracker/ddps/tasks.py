"""Background parsing of uploads (django-tasks)."""

import logging
from pathlib import Path

from django.utils import timezone

from django_tasks import task

from ddp_parser import ParseError, parse, to_dict
from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.services import register_upload

logger = logging.getLogger(__name__)


@task()
def parse_upload(upload_id: int, path: str) -> None:
    """Parse the file at ``path`` into ``Upload.document`` and delete the file, whatever happens:
    uploaded DDPs contain personal data and are never kept.
    """
    try:
        upload = Upload.objects.get(pk=upload_id)
        # mark parsing:
        upload.status = Upload.Status.PARSING
        upload.save(update_fields=["status"])
        try:
            document = parse(Path(path), name=upload.file_name)
        except (ParseError, OSError) as exc:
            _fail(upload, str(exc))
        except Exception:
            _fail(upload, "unexpected error while parsing; see the server log")
            logger.exception("parsing upload %s failed", upload_id)
            raise
        else:
            # mark done:
            upload.document = to_dict(document)
            upload.source_sha256 = document.source.sha256
            upload.size_bytes = document.source.size_bytes
            upload.parser_version = document.parser_version
            upload.parsed_at = timezone.now()
            upload.status = Upload.Status.DONE
            upload.save()
            register_upload(upload)
    finally:
        Path(path).unlink(missing_ok=True)


def _fail(upload: Upload, error: str) -> None:
    upload.status = Upload.Status.FAILED
    upload.error = error
    upload.save(update_fields=["status", "error"])
