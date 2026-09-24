"""Step 4: turn a file's bytes into plain Python values plus parser details.

The pipeline asks ``parser_for(name)`` and never imports a concrete parser. Parsers know nothing
about schematization; they return dicts, lists and scalars in a ``Parsed`` record.
"""

from collections.abc import Callable
from functools import partial
from pathlib import PurePosixPath

from ddp_parser.parsers.base import Parsed
from ddp_parser.parsers.csv import parse_csv
from ddp_parser.parsers.json import parse_js_json, parse_json, parse_json_lines

type Parser = Callable[[bytes], Parsed]

_BY_EXTENSION: dict[str, Parser] = {
    ".json": parse_json,
    ".jsonl": parse_json_lines,
    ".ndjson": parse_json_lines,
    ".js": parse_js_json,
    ".csv": parse_csv,
    ".tsv": partial(parse_csv, tab_separated=True),
}


def parser_for(name: str) -> Parser | None:
    """The parser for a file name (by extension, case-insensitive), or None if unsupported."""
    return _BY_EXTENSION.get(PurePosixPath(name).suffix.lower())


__all__ = ["Parsed", "Parser", "parser_for"]
