"""Derive a privacy-preserving schema document from a DDP (zip or single file).

Public API. Everything outside this module is internal and may be reorganised freely.
The pipeline is described in ``docs/docs/ddp_parser/pipeline.md``; the output format in
``docs/docs/ddp_parser/index.md``.

    from ddp_parser import parse, to_json

    document = parse("export.zip")
    print(to_json(document))
"""

from importlib.metadata import version

from ddp_parser.compare import Comparison, Status, Summary, compare
from ddp_parser.errors import DdpParserError, InvalidDocumentError, ParseError
from ddp_parser.match import Candidate, is_data_point, is_structure, suggest
from ddp_parser.merge import Merged, merge, merge_trees
from ddp_parser.model import (
    Document,
    children,
    from_dict,
    from_json,
    node_from_dict,
    node_to_dict,
    to_dict,
    to_json,
    walk,
)
from ddp_parser.options import Options
from ddp_parser.pipeline import parse
from ddp_parser.schematize.samples import mask

__version__ = version("ddp-parser")

__all__ = [
    "Candidate",
    "Comparison",
    "DdpParserError",
    "Document",
    "InvalidDocumentError",
    "Merged",
    "Options",
    "ParseError",
    "Status",
    "Summary",
    "__version__",
    "children",
    "compare",
    "from_dict",
    "from_json",
    "is_data_point",
    "is_structure",
    "mask",
    "merge",
    "merge_trees",
    "node_from_dict",
    "node_to_dict",
    "parse",
    "suggest",
    "to_dict",
    "to_json",
    "walk",
]
