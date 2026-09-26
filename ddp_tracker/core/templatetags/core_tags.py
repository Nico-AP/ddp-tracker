import json
from collections import Counter
from typing import Any

from django import template

from ddp_tracker.schemas import labels

register = template.Library()


@register.filter
def as_json(value: Any) -> str:  # noqa: ANN401 - any JSON-serialisable value
    """Pretty-printed JSON, for node details."""
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


@register.simple_tag
def plain_type(kind: str, type_: str, path: str, item_type: str = "") -> str:
    """A node's kind and type in plain language (see ``schemas.labels``)."""
    return labels.plain_type(kind, type_, path, item_type)


@register.filter
def ranked(counter: Counter[str]) -> list[tuple[str, int]]:
    """``(value, count)`` pairs, most common first. Templates can't call ``most_common``
    themselves: on a ``Counter``, the attribute lookup finds the missing key ``0`` first.
    """
    return counter.most_common()
