"""JSON, JSON Lines and ``js-json`` (JSON assigned to a variable, e.g.
``window.YTD.tweets.part0 = [...]`` in X/Twitter exports).

A ``.json`` file that is not one JSON value but has one value per line is read as JSON Lines.
"""

import re
from collections.abc import Iterator

import msgspec

from ddp_parser.errors import ParseError
from ddp_parser.parsers.base import Parsed
from ddp_parser.parsers.encoding import decode

# ``name =`` before the JSON: identifiers, dots and bracket access, e.g. ``window.YTD.x.part0 =``.
_JS_ASSIGNMENT = re.compile(r"^\s*(?:(?:var|let|const)\s+)?[A-Za-z_$][\w$.\[\]'\"]*\s*=")


def parse_json(data: bytes) -> Parsed:
    text, encoding = decode(data)
    try:
        return Parsed(parser="json", encoding=encoding, value=_loads(text))
    except ParseError as not_json:
        if text.strip().count("\n") == 0:
            raise
        try:
            items = list(_lines(text))  # validates every line before anything is observed
        except ParseError:
            raise not_json from None
    return Parsed(parser="jsonl", encoding=encoding, items=items)


def parse_json_lines(data: bytes) -> Parsed:
    text, encoding = decode(data)
    return Parsed(parser="jsonl", encoding=encoding, items=_lines(text))


def parse_js_json(data: bytes) -> Parsed:
    text, encoding = decode(data)
    match = _JS_ASSIGNMENT.match(text)
    if match is None:
        msg = "no 'name = <json>' assignment found"
        raise ParseError(msg)
    body = text[match.end() :].strip().removesuffix(";")
    return Parsed(
        parser="js-json", encoding=encoding, value=_loads(body), wrapper=match.group().strip()
    )


def _loads(text: str) -> object:
    try:
        return msgspec.json.decode(text)
    except msgspec.DecodeError as exc:
        raise ParseError(str(exc)) from exc


def _lines(text: str) -> Iterator[object]:
    for line in text.splitlines():
        if line.strip():
            yield _loads(line)
