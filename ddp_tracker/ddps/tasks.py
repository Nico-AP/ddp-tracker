"""Background tasks (django-tasks): parsing uploads, re-normalizing a platform's uploads."""

import logging
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from django_tasks import task

from ddp_parser import ParseError, parse, to_dict
from ddp_tracker.ddps.checks import decide
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.rules import options_for
from ddp_tracker.ddps.values import keep, parse_options, split_values
from ddp_tracker.schemas.services import get_format_of

logger = logging.getLogger(__name__)


@task()
def parse_upload(upload_id: int, path: str, public_key: str = "") -> None:
    """Parse the file at ``path`` into ``Upload.document`` and delete the file, whatever happens:
    uploaded DDPs contain personal data and are never kept. With ``public_key``, a few values per
    data point are kept for the uploader, sealed with it (``ddps/values.py``).
    """
    try:
        upload = Upload.objects.get(pk=upload_id)
        # mark parsing:
        upload.status = Upload.Status.PARSING
        upload.save(update_fields=["status"])
        try:
            platform = upload.platform_id
            options = parse_options(platform) if public_key else options_for(platform)
            document = parse(Path(path), options, name=upload.file_name)
        except (ParseError, OSError) as exc:
            _fail(upload, str(exc))
        except Exception:
            _fail(upload, "unexpected error while parsing; see the server log")
            logger.exception("parsing upload %s failed", upload_id)
            raise
        else:
            parsed_as = get_format_of(document.root)
            if upload.file_format and parsed_as != upload.file_format:
                declared = Upload.FileFormat(upload.file_format).label
                _fail(upload, f"Declared as a {declared}, but the file is {parsed_as.upper()}.")
                return
            # mark done and check it together: never parsed-but-unchecked (ddps/checks.py)
            try:
                with transaction.atomic():
                    data = to_dict(document)
                    values = split_values(data)  # never part of the document
                    upload.document = data
                    upload.source_sha256 = document.source.sha256
                    upload.size_bytes = document.source.size_bytes
                    upload.parser_version = document.parser_version
                    upload.parsed_at = timezone.now()
                    upload.status = Upload.Status.DONE
                    upload.save()
                    if public_key and values:
                        keep(upload, values, public_key)
                    decide(upload)  # registered if plausible, else held
            except Exception:
                _fail(upload, "unexpected error while checking; see the server log")
                logger.exception("checking upload %s failed", upload_id)
                raise
    finally:
        Path(path).unlink(missing_ok=True)


@task()
def renormalize_platform(platform_id: int) -> None:
    """Apply the platform's current path rules to its stored uploads (``schemas/renormalize.py``),
    e.g. after a rule was added in the admin.
    """
    from ddp_tracker.schemas.renormalize import renormalize  # noqa: PLC0415 - schemas imports ddps

    platform = Platform.objects.get(pk=platform_id)
    report = renormalize(platform)
    logger.info(
        "re-normalized %s: %d uploads changed, %d locations moved, %d conflicts",
        platform,
        report.uploads,
        report.moved,
        len(report.conflicts),
    )
    for conflict in report.conflicts:
        logger.warning("re-normalizing %s: %s", platform, conflict)


def _fail(upload: Upload, error: str) -> None:
    upload.status = Upload.Status.FAILED
    upload.error = error
    upload.save(update_fields=["status", "error"])
