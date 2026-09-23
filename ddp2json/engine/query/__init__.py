"""Post-conversion helpers for walking content trees.

Not part of the ZIP → JSON pipeline; import this after you have a report tree.
"""

from .search import walk_leaves

__all__ = ["walk_leaves"]
