from typing import Any

from django.core.management.base import BaseCommand

from ddp_tracker.ddps.values import purge


class Command(BaseCommand):
    """Delete the uploader's values whose retention time (``DDP_VALUES_RETENTION_DAYS``) is over.
    They are unreadable once expired anyway; this removes the sealed data too. Run it daily,
    e.g. from cron::

        uv run manage.py purge_upload_values
    """

    help = "Delete the uploader's values of uploads whose retention time is over."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = purge()
        self.stdout.write(f"Deleted the values of {deleted} upload(s).")
