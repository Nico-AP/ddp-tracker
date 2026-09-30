"""Shared by the journeys tests: a database with the demo data in it."""

import io
import tempfile
from pathlib import Path
from typing import Any

from django.core.management import call_command
from django.test import TestCase, override_settings


def seed_demo(*, force: bool = True, **options: Any) -> str:
    """Run ``seed_demo`` as tests need it: DEBUG is off under test (hence ``force``), and the
    fictional packages wait in a temporary folder, where none may be left afterwards (an
    uploaded package is never kept). Returns what the command printed."""
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as incoming, override_settings(DDP_INCOMING_DIR=incoming):
        call_command("seed_demo", force=force, stdout=out, **options)
        left = list(Path(incoming).iterdir())
    assert not left, f"seed_demo kept uploaded files: {left}"
    return out.getvalue()


class SeededTestCase(TestCase):
    """A test case whose database holds the demo data (seeded once per class)."""

    @classmethod
    def setUpTestData(cls) -> None:
        seed_demo()
