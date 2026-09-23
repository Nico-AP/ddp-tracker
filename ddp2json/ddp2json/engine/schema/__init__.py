"""Privacy-oriented schema trees from full content trees.

HTML projection for schema modes lives in ``engine.schema.html`` (runner) and
``ddp2json.policy.html`` (specs). Scrub field/path policy lives in
``ddp2json.policy.scrub``.
"""

from .html import apply_html_specs, default_specs_dir, load_specs
from .redact import path_template, redact_tree
from .unify import summarize_lists


def to_schema(
    tree: dict,
    *,
    values_mode: str = "none",
    redact_paths: bool = True,
) -> dict:
    """Convert a content tree to descriptors, then summarize uniform lists.

    ``values_mode``:
      - ``none``: type/shape only (default schema mode)
      - ``safe``: short non-PII enums (``--enums``)
      - ``all``: keep every scalar under ``values`` (``--schema-full``)

    ``redact_paths``: when True, scrub identifying keys and media paths.
    """
    return summarize_lists(
        redact_tree(tree, values_mode=values_mode, redact_paths=redact_paths),
        values_mode=values_mode,
    )


__all__ = [
    "to_schema",
    "redact_tree",
    "summarize_lists",
    "path_template",
    "apply_html_specs",
    "default_specs_dir",
    "load_specs",
]
