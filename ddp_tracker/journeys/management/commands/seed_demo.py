import secrets
from collections import Counter
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from ddp_tracker.journeys.demo.seed import SeedError, reset, seed
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL, DEMO_PASSWORD


class Command(BaseCommand):
    """Fictional demo data for a local DDP Tracker (``journeys/demo``): two users, four
    platforms, five uploads, annotations, representations, and a few open items for the
    queues. It only adds what is missing, so it is safe to run again::

        uv run manage.py seed_demo            # create what is missing
        uv run manage.py seed_demo --reset    # remove what it created

    For local demos: it refuses to run when DEBUG is off, unless forced, and then the demo
    users get a random password instead of the documented one.
    """

    help = "Create fictional demo data (platforms, uploads, annotations, representations)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset", action="store_true", help="Remove the demo data instead of creating it."
        )
        parser.add_argument("--force", action="store_true", help="Run although DEBUG is off.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options["force"]:
            msg = "seed_demo is for local demos and DEBUG is off. Use --force if you are sure."
            raise CommandError(msg)
        if options["reset"]:
            self._report("Removed", reset())
            return
        password = DEMO_PASSWORD if settings.DEBUG else secrets.token_urlsafe(12)
        try:
            created = seed(password)
        except SeedError as error:
            raise CommandError(str(error)) from error
        self._report("Created", created)
        users = f"{ADMIN_EMAIL} (staff) or {CURATOR_EMAIL} (not staff)"
        if created["users"]:
            self.stdout.write(f"Log in as {users}. Password for both: {password}")
        else:
            self.stdout.write(
                f"The demo users exist already: {users}. Their passwords are unchanged."
            )

    def _report(self, verb: str, counts: Counter[str]) -> None:
        # every kind is a plural ending in "s": one of a kind drops it ("1 suggestion")
        found = [
            f"{count} {kind.removesuffix('s') if count == 1 else kind}"
            for kind, count in counts.items()
            if count
        ]
        self.stdout.write(f"{verb}: {', '.join(found)}." if found else f"{verb}: nothing.")
