import json
from collections import Counter
from typing import Any

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from ddp_tracker.schemas import labels

register = template.Library()


@register.filter
def as_json(value: Any) -> str:  # noqa: ANN401 - any JSON-serialisable value
    """Pretty-printed JSON, for node details."""
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


@register.filter
def value_label(value: str, field: str) -> str:
    """A kind in plain words ("archive" for a container …); other fields' values as they are."""
    return labels.KIND_NAMES.get(value, value) if field == "kind" else value


@register.filter
def last_part(path: str) -> str:
    """``<item>/date`` → ``date``."""
    return path.rsplit("/", 1)[-1]


@register.filter
def parent_part(path: str) -> str:
    """``<item>/date`` → ``<item>``."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


@register.filter
def path_breaks(path: str) -> str:
    """A path that may wrap after each ``/`` (never inside a key)."""
    lead, rest = ("/", path[1:]) if path.startswith("/") else ("", path)  # no break after it
    return mark_safe(lead + "/<wbr>".join(escape(part) for part in rest.split("/")))  # noqa: S308 - escaped


@register.filter
def ranked(counter: Counter[str]) -> list[tuple[str, int]]:
    """``(value, count)`` pairs, most common first. Templates can't call ``most_common``
    themselves: on a ``Counter``, the attribute lookup finds the missing key ``0`` first.
    """
    return counter.most_common()
