"""HTML projection engine for schema modes (runners only).

Specs live in ``ddp2json/policy/html``. This package loads and applies them.
"""

from .apply import apply_html_specs, find_matching_spec
from .loader import default_specs_dir, load_specs
from .project import project_dom

__all__ = [
    "apply_html_specs",
    "default_specs_dir",
    "find_matching_spec",
    "load_specs",
    "project_dom",
]
