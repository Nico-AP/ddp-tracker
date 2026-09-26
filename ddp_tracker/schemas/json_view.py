"""Where a node sits in its file, as JSON: the keys leading to it, and the object (or list) that
holds it, one key per line. Values are placeholders (``<text>``, ``<text · datetime>``);
objects and lists further away are abbreviated (``{…}``, ``[…]``).

For ``/user_data.json/Your Activity/Watch History/VideoList/[]/Date``::

    {
      "Your Activity": {
        "Watch History": {
          "VideoList": [
            {
              "Date": <text · datetime>,
              "Link": <text · url>,
              "Title": <text · empty>
            }
          ]
        }
      }
    }

The part shown in full is the node itself when it is an object or a list (a list's item opened),
else its parent with the node's siblings. Built from locations and their observations (so it
follows the filter). Display only.
"""

import json

from django.db.models import QuerySet

from ddp_tracker.schemas.models import ITEM, Location, Observation
from ddp_tracker.schemas.profiles import Profile, profiles

_INDENT = "  "


def _ancestors(path: str) -> list[str]:
    """``/a/b/c`` → ``["", "/a", "/a/b", "/a/b/c"]``."""
    parts = path.split("/")
    return ["/".join(parts[:end]) for end in range(1, len(parts) + 1)]


def _is(profile: Profile, json_type: str) -> bool:
    return json_type in set(profile.main_type.split("|")) - {"null"}


def _is_structure(profile: Profile) -> bool:
    return _is(profile, "object") or _is(profile, "array")


def _key(node: Location) -> str:
    return json.dumps(node.name or "", ensure_ascii=False) + ": "


def json_path(location: Location, observations: QuerySet[Observation]) -> str | None:
    """The JSON around ``location``, or None outside parsed files (folders, media …)."""
    chain = sorted(
        Location.objects.filter(platform=location.platform_id, path__in=_ancestors(location.path)),
        key=lambda node: node.path.count("/") if node.path else -1,
    )
    found = profiles((node.pk for node in chain), observations)
    files = [index for index, node in enumerate(chain) if found[node.pk].main_kind == "file"]
    if not files:
        return None
    levels = chain[files[-1] :]  # the file, the keys below it, …, the node
    shows_itself = len(levels) == 1 or _is_structure(found[location.pk])
    container = levels[-1] if shows_itself else levels[-2]
    block = _Block(container, observations).lines()
    outer = levels[: levels.index(container) + 1]
    for depth in range(len(outer) - 2, -1, -1):  # wrap it in the keys leading to it
        parent, child = outer[depth], outer[depth + 1]
        opening, closing = ("[", "]") if _is(found[parent.pk], "array") else ("{", "}")
        key = "" if child.path.endswith(ITEM) else _key(child)
        block = [
            opening,
            _INDENT + key + block[0],
            *(_INDENT + line for line in block[1:]),
            closing,
        ]
    return "\n".join(block)


class _Block:
    """An object or list, one child per line; a list's item object is opened too."""

    def __init__(self, container: Location, observations: QuerySet[Observation]) -> None:
        observed = Location.objects.filter(
            platform=container.platform_id, observations__in=observations
        ).distinct()
        below = list(observed.filter(parent_path=container.path))
        items = [node.path for node in below if node.path.endswith(ITEM)]
        below += list(observed.filter(parent_path__in=items))  # the fields of a list's item
        below.sort(key=lambda node: (node.position, node.path))
        self.below = below
        self.found = profiles([container.pk, *(node.pk for node in below)], observations)
        self.container = container

    def lines(self, node: Location | None = None) -> list[str]:
        node = node or self.container
        children = [child for child in self.below if child.parent_path == node.path]
        if _is(self.found[node.pk], "array"):
            item = next((child for child in children if child.path.endswith(ITEM)), None)
            if item is None:
                return ["[]"]
            inner = self.lines(item) if _is(self.found[item.pk], "object") else [self.value(item)]
            return ["[", *(_INDENT + line for line in inner), "]"]
        if not children:
            return ["{}"] if _is(self.found[node.pk], "object") else [self.value(node)]
        lines = ["{"]
        for index, child in enumerate(children):
            comma = "," if index < len(children) - 1 else ""
            lines.append(f"{_INDENT}{_key(child)}{self.value(child)}{comma}")
        return [*lines, "}"]

    def value(self, node: Location) -> str:
        """A child on its parent's line: a placeholder, or an abbreviated object or list."""
        profile = self.found[node.pk]
        if _is(profile, "array"):
            return "[…]" if profile.has_children else "[]"
        if _is(profile, "object"):
            return "{…}" if profile.has_children else "{}"
        return "<" + " · ".join(part for part in (profile.label, profile.shape_hint) if part) + ">"
