from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from ddp_parser import from_dict, is_data_point, walk
from ddp_tracker.ddps.models import Upload
from ddp_tracker.schemas.services import suggest_for


# TODO: Why is this needed exactly?
class Command(BaseCommand):
    help = (
        "Re-apply the parser's current rules to the observations of all registered uploads "
        "(e.g. which nodes are data points) and recompute their suggestions, from the stored "
        "schema documents."
    )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        changed = 0
        for upload in Upload.objects.filter(registered_at__isnull=False, document__isnull=False):
            assert upload.document is not None
            flags = {
                node.path: is_data_point(node) for node in walk(from_dict(upload.document).root)
            }
            for observation in upload.observations.select_related("location"):
                flag = flags.get(observation.location.path, False)
                if observation.is_data_point != flag:
                    observation.is_data_point = flag
                    observation.save(update_fields=["is_data_point"])
                    changed += 1
            suggest_for(upload)
        self.stdout.write(f"Updated {changed} observation{'s' if changed != 1 else ''}.")
