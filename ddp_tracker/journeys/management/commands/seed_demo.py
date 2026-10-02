import secrets
from collections import Counter
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

import environ

from ddp_tracker.journeys.demo.seed import SeedError, reset, seed
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL

# the environment variable that holds the demo users' password
LOGIN_VARIABLE = "DJANGO_DEMO_PASSWORD"


class Command(BaseCommand):
    """Fictional demo data for a local DDP Tracker (``journeys/demo``): two users, four
    platforms, five uploads, annotations, representations, and a few open items for the
    queues. It only adds what is missing, so it is safe to run again::

        uv run manage.py seed_demo            # create what is missing
        uv run manage.py seed_demo --reset    # remove what it created

    For local demos: it refuses to run when DEBUG is off, unless forced. Both demo users get
    the password in the environment variable ``DJANGO_DEMO_PASSWORD``, or a random one when it
    is not set or empty; the command prints it once, and where it came from.
    """

    help = (
        "Create fictional demo data (platforms, uploads, annotations, representations). "
        f"The demo users' password is {LOGIN_VARIABLE}, or a random one if that is not set."
    )

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
        password, source = self._password()
        try:
            created = seed(password)
        except SeedError as error:
            raise CommandError(str(error)) from error
        self._report("Created", created)
        users = f"{ADMIN_EMAIL} (staff) or {CURATOR_EMAIL} (not staff)"
        if created["users"]:
            self.stdout.write(f"Log in as {users}. Password for both: {password}")
            self.stdout.write(f"The password is {source}.")
        else:
            self.stdout.write(
                f"The demo users exist already: {users}. Their passwords are unchanged."
            )

    def _password(self) -> tuple[str, str]:
        """The demo users' password, and where it came from (in words)."""
        # read like the settings read theirs, but here: only this command needs it
        password = environ.Env().str(LOGIN_VARIABLE, default="")
        if password:
            return password, f"from {LOGIN_VARIABLE}"
        return (
            secrets.token_urlsafe(12),
            f"made up at random; set {LOGIN_VARIABLE} to choose your own",
        )

    def _report(self, verb: str, counts: Counter[str]) -> None:
        # every kind is a plural ending in "s": one of a kind drops it ("1 suggestion")
        found = [
            f"{count} {kind.removesuffix('s') if count == 1 else kind}"
            for kind, count in counts.items()
            if count
        ]
        self.stdout.write(f"{verb}: {', '.join(found)}." if found else f"{verb}: nothing.")
