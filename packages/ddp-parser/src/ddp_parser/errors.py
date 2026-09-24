"""Exception types raised inside the pipeline.

``pipeline`` catches these and turns them into ``unmatched`` nodes or document ``warnings``,
so no broad ``except Exception`` is needed anywhere.
"""


class DdpParserError(Exception):
    """Base class for all errors raised by this package."""


class InvalidPathError(DdpParserError, ValueError):
    """A path that is not a valid JSON Pointer (spec 2.3)."""


class InvalidDocumentError(DdpParserError, ValueError):
    """A serialised document (dict / JSON) that cannot be read back into the model."""


class ParseError(DdpParserError):
    """A file that could not be read by the parser chosen for it (becomes ``parse_error``)."""


class LimitExceededError(DdpParserError):
    """An entry that would exceed a safety limit (becomes ``too_large``)."""
