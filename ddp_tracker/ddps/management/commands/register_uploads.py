from typing import Any

from django.core.management.base import BaseCommand

from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.services import register_upload


# TODO: May be removed?
class Command(BaseCommand):
    help = "Add parsed uploads that aren't registered yet to their platform's collected schema."

    def handle(self, *args: Any, **options: Any) -> None:
        pending = Upload.objects.filter(status=Upload.Status.DONE, registered_at__isnull=True)
        count = 0
        for upload in pending.order_by("requested_at", "created_at"):
            register_upload(upload)
            count += 1
        self.stdout.write(f"Registered {count} upload{'s' if count != 1 else ''}.")
