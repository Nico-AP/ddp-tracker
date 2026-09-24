"""Derive a privacy-preserving schema document from a DDP (zip or single file).

Public API. Everything outside this module is internal and may be reorganised freely.
The pipeline is described in ``docs/docs/ddp_parser/pipeline.md``; the output format in
``docs/docs/ddp_parser/index.md``.

    from ddp_parser import parse, to_json

    document = parse("export.zip")
    print(to_json(document))
"""

from importlib.metadata import version

from ddp_parser.errors import DdpParserError, InvalidDocumentError, ParseError
from ddp_parser.model import Document, from_dict, from_json, to_dict, to_json
from ddp_parser.options import Options
from ddp_parser.pipeline import parse

__version__ = version("ddp-parser")

__all__ = [
    "DdpParserError",
    "Document",
    "InvalidDocumentError",
    "Options",
    "ParseError",
    "__version__",
    "from_dict",
    "from_json",
    "parse",
    "to_dict",
    "to_json",
]
