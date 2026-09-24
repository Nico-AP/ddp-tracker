"""``Parsed``: what every parser returns.

Parsers turn a file's bytes into plain Python values (dicts, lists, scalars) and know nothing
about schematization. A file is either one value, or an array whose items are produced lazily
(CSV rows, JSON Lines) so the pipeline can stream them into a ``NodeBuilder``.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from ddp_parser.model import CsvInfo


@dataclass(frozen=True, slots=True, kw_only=True)
class Parsed:
    parser: str  # spec §6: "json", "jsonl", "js-json", "csv"
    encoding: str
    value: object = None
    items: Iterable[object] | None = None  # set instead of ``value`` for streamed arrays
    csv: CsvInfo | None = None
    wrapper: str | None = None
