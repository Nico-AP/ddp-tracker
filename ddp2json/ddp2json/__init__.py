"""Convert DDP ZIP archives into nested JSON content trees.

Public entry points re-export from ``ddp2json.engine``. Prescriptions
(HTML specs, scrub rules) live under ``ddp2json.policy``.
"""

from ._version import __version__
from .engine import main, process_archive, process_folder

__all__ = [
    "__version__",
    "main",
    "process_folder",
    "process_archive",
]
