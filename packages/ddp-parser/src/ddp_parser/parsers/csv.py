"""CSV / TSV: dialect sniffing, header cleanup, cell type inference; one dict per row.

Spec: sections 3.2 and 4.2. The first row is always the header. Rows are produced lazily from
the decoded text, so a large file is never held as Python objects all at once.
"""

import csv
import io
import re
from collections.abc import Iterator

from ddp_parser.errors import ParseError
from ddp_parser.model import CsvInfo
from ddp_parser.parsers.base import Parsed
from ddp_parser.parsers.encoding import decode

_SNIFF_BYTES = 64 * 1024
_DELIMITERS = ",;\t|"

_INTEGER = re.compile(r"^[+-]?(0|[1-9]\d*)$")  # no leading zeros: "007" stays a string
_NUMBER = re.compile(r"^[+-]?(0|[1-9]\d*)?(\.\d+)?([eE][+-]?\d+)?$")
_BOOLEANS = {"true": True, "false": False}

type Cell = str | int | float | bool


def parse_csv(data: bytes, *, tab_separated: bool = False) -> Parsed:
    text, encoding = decode(data)
    dialect = _sniff(text[:_SNIFF_BYTES], tab_separated=tab_separated)
    reader = csv.reader(io.StringIO(text, newline=""), dialect)
    try:
        header = next(reader)
    except StopIteration:
        header = []
    except csv.Error as exc:
        raise ParseError(str(exc)) from exc
    return Parsed(
        parser="csv",
        encoding=encoding,
        items=_rows(reader, clean_header(header)),
        csv=CsvInfo(delimiter=dialect.delimiter, quotechar=dialect.quotechar or '"'),
    )


def clean_header(names: list[str]) -> list[str]:
    """Make column names usable as keys: blanks become ``column_<n>`` (1-based), repeats get
    ``_2``, ``_3`` … so no column overwrites another.
    """
    seen: dict[str, int] = {}
    cleaned: list[str] = []
    for position, raw in enumerate(names, start=1):
        name = raw.strip() or f"column_{position}"
        seen[name] = seen.get(name, 0) + 1
        cleaned.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return cleaned


def infer(cell: str) -> Cell:
    """Spec 3.2: integers, numbers and ``true``/``false`` become typed values."""
    if _INTEGER.match(cell):
        return int(cell)
    if _NUMBER.match(cell) and any(char.isdigit() for char in cell):
        return float(cell)
    return _BOOLEANS.get(cell.lower(), cell)


def _rows(reader: Iterator[list[str]], header: list[str]) -> Iterator[dict[str, Cell]]:
    try:
        for cells in reader:
            if not cells:
                continue  # blank line
            names = header + [f"column_{n}" for n in range(len(header) + 1, len(cells) + 1)]
            yield {name: infer(cell) for name, cell in zip(names, cells, strict=False)}
    except csv.Error as exc:
        raise ParseError(str(exc)) from exc


def _sniff(sample: str, *, tab_separated: bool) -> type[csv.Dialect]:
    if tab_separated:
        return csv.excel_tab
    try:
        return csv.Sniffer().sniff(sample, delimiters=_DELIMITERS)
    except csv.Error:
        return csv.excel
