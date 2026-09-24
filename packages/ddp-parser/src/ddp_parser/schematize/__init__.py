"""Steps 5-6: aggregate observed values into schema nodes.

Values are observed one at a time into ``NodeBuilder``s and never kept, so memory grows with the
schema, not with the export.
"""

from ddp_parser.schematize.builder import NodeBuilder, data_fields

__all__ = ["NodeBuilder", "data_fields"]
