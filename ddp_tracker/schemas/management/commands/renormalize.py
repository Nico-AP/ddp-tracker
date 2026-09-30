from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.renormalize import renormalize


class Command(BaseCommand):
    """Apply each platform's current path rules (``PathRule``) and the wrapper-folder check to
    its stored uploads, and move the curation of renamed locations (``schemas/renormalize.py``).
    Saving a rule in the admin does this for its platform in the background; run this after
    upgrading the parser, or to see first what a rule would change::

        uv run manage.py renormalize --platform tiktok --dry-run

    Only new paths are printed: the old ones can hold usernames.
    """

    help = "Apply the platforms' current path rules to their stored uploads."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--platform", metavar="SLUG", help="only this platform")
        parser.add_argument("--dry-run", action="store_true", help="only show what would change")

    def handle(self, *args: Any, **options: Any) -> None:
        platforms = Platform.objects.all()
        if options["platform"]:
            platforms = platforms.filter(slug=options["platform"])
            if not platforms.exists():
                msg = f"no platform {options['platform']!r}"
                raise CommandError(msg)
        for platform in platforms:
            report = renormalize(platform, dry_run=options["dry_run"])
            if options["dry_run"]:
                summary = f"would change {report.uploads} upload(s)"
            else:
                summary = f"changed {report.uploads} upload(s), moved {report.moved} location(s)"
            self.stdout.write(f"{platform}: {summary}, {len(report.paths)} renamed path(s)")
            for path in sorted(report.paths):
                self.stdout.write(f"  {path or '/'}")  # "" is the root
            for conflict in report.conflicts:
                self.stdout.write(self.style.WARNING(f"  conflict: {conflict}"))
