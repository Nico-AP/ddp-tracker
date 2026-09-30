"""The parser options of a platform: its path rules (``PathRule``) on top of the defaults."""

from typing import Any

from ddp_parser import Options
from ddp_tracker.ddps.models import PathRule, Platform


def options_for(platform: Platform | int, **options: Any) -> Options:
    """``Options(**options)`` with ``platform``'s variable and kept keys."""
    rules = PathRule.objects.filter(platform=platform).values_list("kind", "pattern")
    by_kind: dict[str, list[str]] = {}
    for kind, pattern in rules:
        by_kind.setdefault(kind, []).append(pattern)
    return Options(
        variable_keys=tuple(by_kind.get(PathRule.Kind.VARIABLE_KEY, ())),
        keep_keys=tuple(by_kind.get(PathRule.Kind.KEEP_KEY, ())),
        **options,
    )
