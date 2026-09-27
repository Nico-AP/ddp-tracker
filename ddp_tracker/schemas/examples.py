"""A location's example values (``Location.example_values``), each with where it came from.

``[{"value": "Jane Doe", "source": "user_input"}, {"value": "2024-02-02", "source": "extracted"}]``

- ``extracted``: contributed as is by an uploader from the values found in their file
  (``ddps/values.py``); never edited.
- ``user_input``: typed by a curator in the examples form.
"""

import json
from typing import TypedDict

from ddp_tracker.schemas.models import Location

EXTRACTED = "extracted"
USER_INPUT = "user_input"


class Example(TypedDict):
    value: str
    source: str


def as_text(value: str | float | bool) -> str:
    """An example's text: strings as they are, other values as JSON (``true``, ``5``)."""
    return value if isinstance(value, str) else json.dumps(value)


def of_source(location: Location, source: str) -> list[str]:
    return [example["value"] for example in location.example_values if example["source"] == source]


def add_examples(location: Location, values: list[str], source: str) -> None:
    """Append ``values`` (stripped, non-empty, not there yet) with ``source``."""
    examples: list[Example] = list(location.example_values)
    known = {example["value"] for example in examples}
    for value in (value.strip() for value in values):
        if value and value not in known:
            examples.append({"value": value, "source": source})
            known.add(value)
    if examples != location.example_values:
        location.example_values = examples
        location.save(update_fields=["example_values"])


def set_examples(location: Location, extracted: list[str], typed: list[str]) -> None:
    """Keep the ``extracted`` examples among the location's own (they are never edited, only
    removed), and replace the typed ones with ``typed``."""
    keep = set(extracted)
    location.example_values = [
        example
        for example in location.example_values
        if example["source"] == EXTRACTED and example["value"] in keep
    ]
    add_examples(location, typed, USER_INPUT)
    location.save(update_fields=["example_values"])


def preview(location: Location, count: int) -> tuple[list[str], int]:
    """The location's first ``count`` examples, and how many more there are."""
    values = [example["value"] for example in location.example_values]
    return values[:count], max(len(values) - count, 0)
