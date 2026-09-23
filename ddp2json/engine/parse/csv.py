"""Parse CSV files into a nested tree of data leaves.

Each column is a list node; each cell is a data leaf:

    {
      "<column>": {
        "kind": "list",
        "items": {
          "0": {"kind": "data", "value": "..."},
          "1": {"kind": "data", "value": "..."},
          ...
        }
      },
      ...
    }
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..tree.nodes import data_leaf, list_node


def dedupe_headers(headers: list[str]) -> list[str]:
    """Make column names unique so no column is silently overwritten."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for i, name in enumerate(headers):
        name = name or f"column_{i}"
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            result.append(name)
    return result


def parse_csv_tree(file_path: Path) -> dict:
    """Parse one CSV into {column: list_node of data leaves}."""
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return {}

        headers = dedupe_headers(raw_headers)
        columns: dict[str, dict] = {h: {} for h in headers}

        for row_idx, row in enumerate(reader):
            key = str(row_idx)
            for col_idx, header in enumerate(headers):
                value = row[col_idx] if col_idx < len(row) else ""
                columns[header][key] = data_leaf(value)

    return {header: list_node(items) for header, items in columns.items()}
