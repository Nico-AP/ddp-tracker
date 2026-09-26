"""Plain-language labels for nodes ("list of objects", "group of keys", "each item: text").

Display only: paths and the stored kinds and types stay technical (see docs/tracker/concepts.md,
"How nodes are labelled").
"""

_ITEMS = "/[]"
_KINDS = {
    "container": "archive",
    "folder": "folder",
    "media": "media file",
    "unmatched": "unreadable file",
}
# JSON type → (singular, plural)
_TYPES = {
    "string": ("text", "texts"),
    "integer": ("integer", "integers"),
    "number": ("number", "numbers"),
    "boolean": ("true/false", "true/false values"),
    "object": ("object", "objects"),
    "array": ("list", "lists"),
}


def _types(type_: str) -> tuple[list[str], bool]:
    """The non-null types of a union like ``null|string``, and whether it may be empty."""
    parts = [part for part in type_.split("|") if part]
    return [part for part in parts if part != "null"], "null" in parts


def _join(names: list[str]) -> str:
    return " or ".join(names)


def _value(type_: str, path: str, *, empty: bool = False) -> str:
    """A value, an object or a mix of them, in words. ``empty``: an object never seen with keys."""
    types, nullable = _types(type_)
    if not types:
        return "empty" if nullable else ""
    if types == ["object"]:
        label = "object" if path.endswith(_ITEMS) else "group of keys"
        if empty:
            return f"{label} (always empty so far)"
    else:
        label = _join([_TYPES.get(name, (name, name))[0] for name in types])
    return f"{label} (or empty)" if nullable else label


def _list(item_type: str) -> str:
    types, _ = _types(item_type)
    if not types:
        return "list (always empty so far)"
    return "list of " + _join([_TYPES.get(name, (name, name))[1] for name in types])


def plain_type(
    kind: str, type_: str, path: str, item_type: str = "", *, empty: bool = False
) -> str:
    """How a node reads to a person: a list with what its items are, a group of keys (an object
    that only groups keys; a list's item object stays "object"), a value in words, or what a
    file is. ``empty``: the node never had children (an object always seen as ``{}``).
    """
    if kind in _KINDS:
        return _KINDS[kind]
    types, nullable = _types(type_)
    if types == ["array"]:
        label = _list(item_type) + (" (or empty)" if nullable else "")
    elif "array" in types:  # sometimes a list, sometimes something else
        others = _value("|".join(name for name in types if name != "array"), path)
        label = f"{_list(item_type)} or {others}"
    else:
        label = _value(type_, path, empty=empty)
    if kind == "file":
        return f"file: {label}" if label else "file"
    return label  # a list's item is named "each item" (Location.display_name): its type is enough
