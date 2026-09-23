"""Runtime engines: tree build, parse, schema, report, query, CLI.

Prescriptions live in ``ddp2json.policy`` — edit those for HTML specs and
scrub rules. This package is the code that runs them.
"""

from .cli import main, process_folder
from .pipeline import process_archive

__all__ = [
    "main",
    "process_folder",
    "process_archive",
]
