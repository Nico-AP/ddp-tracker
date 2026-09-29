"""Default ``ddp_parser`` options for upload parsing in the tracker."""

from typing import Any

from ddp_parser import Options


def default_parse_options(**overrides: Any) -> Options:
    """Parser options for stored schema documents (paths redacted by default)."""
    return Options(redact_paths=True, **overrides)
