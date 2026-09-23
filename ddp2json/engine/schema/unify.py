"""Merge and summarize schema nodes (equality, unify, list collapse)."""

from __future__ import annotations

from ..tree.nodes import is_leaf, is_list
from .describe import merge_enum_values

# Soft shapes that may vary across otherwise identical list items
# (e.g. short "hi" → alpha vs longer message → text).
# Note: date/decimal are NOT soft — they must stay distinct from free text.
_SOFT_STRING_SHAPES = frozenset(
    {
        "empty",
        "alpha",
        "alphanumeric",
        "text",
        "other",
        "digits",
        "hex",
    }
)


def _shape_set(shape) -> set[str]:
    if shape is None:
        return set()
    if isinstance(shape, list):
        return set(shape)
    return {shape}


def _shapes_compatible(a, b, type_: str | None) -> bool:
    sa, sb = _shape_set(a), _shape_set(b)
    if sa == sb:
        return True
    if type_ != "string":
        return False
    if sa and sb and sa <= _SOFT_STRING_SHAPES and sb <= _SOFT_STRING_SHAPES:
        return True
    # Blank / missing cells often share a field with typed values.
    if sa == {"empty"} or sb == {"empty"}:
        return True
    return False


def _merge_shapes(a, b):
    merged = sorted(_shape_set(a) | _shape_set(b))
    if not merged:
        return None
    return merged[0] if len(merged) == 1 else merged


def _length_span(value) -> tuple[int, int] | None:
    """Normalize a length or size field to (min, max)."""
    if value is None:
        return None
    if isinstance(value, dict) and "min" in value and "max" in value:
        return int(value["min"]), int(value["max"])
    if isinstance(value, (int, float)):
        n = int(value)
        return n, n
    return None


def _merge_span(a, b) -> dict | int | None:
    """Merge two length/size values into an int or {min, max}."""
    sa, sb = _length_span(a), _length_span(b)
    if sa is None:
        return b
    if sb is None:
        return a
    lo, hi = min(sa[0], sb[0]), max(sa[1], sb[1])
    return lo if lo == hi else {"min": lo, "max": hi}


def _is_object(node) -> bool:
    """True for plain object/dir dicts (not leaves, lists, or variants)."""
    return (
        isinstance(node, dict)
        and not is_leaf(node)
        and not is_list(node)
        and node.get("kind") != "variants"
    )


def _mark_optional(node: dict) -> dict:
    out = dict(node)
    out["optional"] = True
    return out


def _variants(nodes: list, *, values_mode: str = "safe") -> dict:
    """Deduplicate incompatible schemas into a variants node."""
    options: list = []
    for n in nodes:
        merged_into = False
        for i, existing in enumerate(options):
            if schema_equal(n, existing):
                merged = schema_merge(existing, n, values_mode=values_mode)
                options[i] = merged if merged is not None else existing
                merged_into = True
                break
        if not merged_into:
            options.append(n)
    return {"kind": "variants", "options": options}


def _formats_compatible(a, b) -> bool:
    """True if formats match, or either side omitted ``format``."""
    fa, fb = a.get("format"), b.get("format")
    if fa is None or fb is None:
        return True
    return fa == fb


def _merge_format(a, b):
    """Keep shared format; prefer the side that has one; never invent a merge."""
    fa, fb = a.get("format"), b.get("format")
    if fa is not None and fb is not None:
        return fa if fa == fb else None
    return fa if fa is not None else fb


def schema_equal(a, b) -> bool:
    """True if two schema nodes have the same structure (lengths may differ)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a == b

    if is_leaf(a) or is_leaf(b):
        if a.get("kind") != b.get("kind"):
            return False
        if a.get("kind") == "data":
            return (
                a.get("type") == b.get("type")
                and _shapes_compatible(a.get("shape"), b.get("shape"), a.get("type"))
                and _formats_compatible(a, b)
            )
        if a.get("kind") == "media" or a.get("kind") == "unmatched":
            return (
                a.get("kind") == b.get("kind")
                and a.get("ext") == b.get("ext")
                and a.get("mime") == b.get("mime")
            )
        return False

    if is_list(a) or is_list(b):
        if not (is_list(a) and is_list(b)):
            return False
        # Summarized lists: compare representative item.
        if "item" in a or "item" in b:
            if "item" not in a or "item" not in b:
                return False
            return schema_equal(a["item"], b["item"])
        items_a = a.get("items") or {}
        items_b = b.get("items") or {}
        if set(items_a) != set(items_b):
            return False
        return all(schema_equal(items_a[k], items_b[k]) for k in items_a)

    if not (_is_object(a) and _is_object(b)):
        return False
    if set(a) != set(b):
        return False
    return all(schema_equal(a[k], b[k]) for k in a)


def schema_merge(a, b, *, values_mode: str = "safe"):
    """Merge two compatible schema nodes (union length/size spans)."""
    optional = bool(a.get("optional") or b.get("optional"))

    if is_leaf(a) and a.get("kind") == "data":
        out = {
            "kind": "data",
            "type": a.get("type"),
            "shape": _merge_shapes(a.get("shape"), b.get("shape")),
        }
        if "length" in a or "length" in b:
            out["length"] = _merge_span(a.get("length"), b.get("length"))
        fmt = _merge_format(a, b)
        if fmt is not None:
            out["format"] = fmt
        # Keep enum/key values only when every merged leaf contributed some;
        # if either side omitted values (free text / sensitive), drop them.
        if "values" in a and "values" in b:
            merged_vals = merge_enum_values(
                a.get("values"), b.get("values"), values_mode=values_mode
            )
            if merged_vals is not None:
                out["values"] = merged_vals
        if optional:
            out["optional"] = True
        return out

    if is_leaf(a) and a.get("kind") in ("media", "unmatched"):
        out = {
            "kind": a.get("kind"),
            "ext": a.get("ext"),
            "mime": a.get("mime"),
            "size": _merge_span(a.get("size"), b.get("size")),
        }
        if optional:
            out["optional"] = True
        return out

    if is_list(a):
        if "item" in a and "item" in b:
            out = {
                "kind": "list",
                "length": _merge_span(a.get("length"), b.get("length")),
                "item": schema_merge(a["item"], b["item"], values_mode=values_mode),
            }
            if optional:
                out["optional"] = True
            return out
        items_a = a.get("items") or {}
        items_b = b.get("items") or {}
        keys = set(items_a) | set(items_b)
        if keys != set(items_a) or keys != set(items_b):
            # Fall back to unify for partial list items — shouldn't be common.
            return None
        out = {
            "kind": "list",
            "items": {
                k: schema_merge(items_a[k], items_b[k], values_mode=values_mode)
                for k in items_a
            },
        }
        if optional:
            out["optional"] = True
        return out

    # Plain objects: exact key match (union merge is handled by unify_schemas).
    out = {k: schema_merge(a[k], b[k], values_mode=values_mode) for k in a}
    if optional:
        out["optional"] = True
    return out


def unify_schemas(nodes: list, *, values_mode: str = "safe"):
    """Merge a list of schema nodes into one, marking missing object fields optional.

    Incompatible shapes become {"kind": "variants", "options": [...]} instead of
    failing the whole parent list/object.
    """
    if not nodes:
        return None
    if len(nodes) == 1:
        return nodes[0]

    if all(is_leaf(n) for n in nodes):
        if not all(schema_equal(nodes[0], n) for n in nodes[1:]):
            return _variants(nodes, values_mode=values_mode)
        merged = nodes[0]
        for n in nodes[1:]:
            merged = schema_merge(merged, n, values_mode=values_mode)
            if merged is None:
                return _variants(nodes, values_mode=values_mode)
        return merged

    if all(is_list(n) for n in nodes):
        items = []
        lengths = []
        for n in nodes:
            if "item" in n:
                items.append(n["item"])
                lengths.append(n.get("length", 0))
            else:
                raw = list((n.get("items") or {}).values())
                if not raw:
                    lengths.append(0)
                    continue
                sub = unify_schemas(raw, values_mode=values_mode)
                items.append(
                    sub if sub is not None else _variants(raw, values_mode=values_mode)
                )
                lengths.append(len(raw))
        if not items:
            return {"kind": "list", "length": 0}
        item = unify_schemas(items, values_mode=values_mode)
        if item is None:
            item = _variants(items, values_mode=values_mode)
        length = lengths[0]
        for L in lengths[1:]:
            length = _merge_span(length, L)
        return {"kind": "list", "length": length, "item": item}

    if all(_is_object(n) for n in nodes):
        return _unify_objects(nodes, values_mode=values_mode)

    # Mixed kinds (e.g. string content vs object share payload).
    return _variants(nodes, values_mode=values_mode)


def _unify_objects(objs: list[dict], *, values_mode: str = "safe") -> dict:
    """Union object keys; fields absent from some items become optional."""
    all_keys: set[str] = set()
    for o in objs:
        all_keys |= {k for k in o.keys() if k != "optional"}

    out: dict = {}
    for key in sorted(all_keys):
        present = [o[key] for o in objs if key in o]
        if not present:
            continue
        child = unify_schemas(present, values_mode=values_mode)
        if child is None:
            child = _variants(present, values_mode=values_mode)
        if len(present) < len(objs):
            child = _mark_optional(child)
        out[key] = child
    return out


def summarize_lists(node, *, values_mode: str = "safe"):
    """Collapse lists into {length, item} when items can be unified."""
    if not isinstance(node, dict):
        return node

    if is_leaf(node) or node.get("kind") == "variants":
        return node

    if is_list(node):
        # Already summarized.
        if "item" in node and "items" not in node:
            return {
                "kind": "list",
                "length": node.get("length", 0),
                "item": summarize_lists(node["item"], values_mode=values_mode),
            }

        raw_items = node.get("items") or {}
        items = {
            str(k): summarize_lists(v, values_mode=values_mode)
            for k, v in raw_items.items()
        }
        if not items:
            return {"kind": "list", "length": 0}

        values = list(items.values())
        unified = unify_schemas(values, values_mode=values_mode)
        if unified is not None:
            return {"kind": "list", "length": len(values), "item": unified}

        # Last resort: still collapse under variants so huge threads don't stay expanded.
        return {
            "kind": "list",
            "length": len(values),
            "item": _variants(values, values_mode=values_mode),
        }

    return {k: summarize_lists(v, values_mode=values_mode) for k, v in node.items()}
