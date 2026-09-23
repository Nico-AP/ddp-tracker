"""Rebuild a BeautifulSoup tree from a stored DOM and run CSS projections."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from ...tree.nodes import data_leaf, is_list, list_node


def _data_value(node) -> str:
    """String from a data leaf, or a plain string structural field."""
    if isinstance(node, dict) and node.get("kind") == "data":
        value = node.get("value")
        return "" if value is None else str(value)
    if isinstance(node, str):
        return node
    return ""


def _attr_string(value) -> str:
    """Attr value from a plain string or legacy data-leaf encoding."""
    if isinstance(value, str):
        return value
    return _data_value(value)


def dom_to_soup(dom: dict) -> BeautifulSoup:
    """Rebuild a BeautifulSoup document from a stored DOM object node."""
    soup = BeautifulSoup("", "html.parser")
    root = _dom_to_tag(dom, soup)
    if root is not None:
        soup.append(root)
    return soup


def _dom_to_tag(dom: dict, soup: BeautifulSoup) -> Tag | None:
    # Collapsed text-only nodes are data leaves; wrap as a span for select().
    if isinstance(dom, dict) and dom.get("kind") == "data":
        tag = soup.new_tag("span")
        tag.append(_data_value(dom))
        return tag

    if not isinstance(dom, dict) or "tag" not in dom:
        return None
    tag_name = _attr_string(dom.get("tag")) or "div"
    tag = soup.new_tag(tag_name)
    attrs = dom.get("attrs") or {}
    if isinstance(attrs, dict):
        for name, val in attrs.items():
            tag[str(name)] = _attr_string(val)

    children = dom.get("children")
    if is_list(children):
        items = children.get("items") or {}
        for key in sorted(
            items.keys(), key=lambda k: int(k) if str(k).isdigit() else str(k)
        ):
            child = items[key]
            if isinstance(child, dict) and child.get("kind") == "data":
                tag.append(_data_value(child))
            elif isinstance(child, dict) and "tag" in child:
                nested = _dom_to_tag(child, soup)
                if nested is not None:
                    tag.append(nested)
    return tag


def _take_from_element(el: Tag, rule: dict) -> str:
    """Read text or a named attribute from ``el`` according to ``rule['take']``."""
    take = rule.get("take", "text")
    if take == "attr":
        name = rule.get("name") or ""
        value = el.get(name)
        if isinstance(value, list):
            return " ".join(str(v) for v in value)
        return "" if value is None else str(value)
    # default: text
    return el.get_text(strip=True)


def _resolve_target(el: Tag, rule: dict) -> Tag | None:
    """Return ``el``, or the first match of a nested ``select`` within ``el``."""
    select = rule.get("select")
    if not select:
        return el
    matches = el.select(select)
    return matches[0] if matches else None


def _project_field_value(el: Tag, rule: dict) -> dict:
    """Project one field rule, optionally scoping via nested ``select``."""
    target = _resolve_target(el, rule)
    if target is None:
        return data_leaf("")
    return data_leaf(_take_from_element(target, rule))


def _project_fields(el: Tag, fields: dict) -> dict:
    """Project a ``fields`` map for one list item element into data leaves."""
    out: dict = {}
    for field_name, field_rule in fields.items():
        if not isinstance(field_rule, dict):
            continue
        out[str(field_name)] = _project_field_value(el, field_rule)
    return out


def project_dom(dom: dict, extract: dict) -> dict:
    """Apply an extract map to a DOM; return a plain object of data/list nodes.

    Field rules inside a ``take: list`` block may include a nested ``select``
    to read a descendant of each matched item (e.g. author/body/timestamp).
    """
    soup = dom_to_soup(dom)
    root = soup.find(True)
    if root is None:
        root = soup

    projected: dict = {}
    for field_name, rule in extract.items():
        if not isinstance(rule, dict):
            continue
        select = rule.get("select") or ""
        take = rule.get("take", "text")
        matches = root.select(select) if select else []

        if take == "list":
            fields = rule.get("fields") or {}
            items: dict = {}
            for i, el in enumerate(matches):
                if fields:
                    items[str(i)] = _project_fields(el, fields)
                else:
                    items[str(i)] = data_leaf(el.get_text(strip=True))
            projected[str(field_name)] = list_node(items)
            continue

        # Single value: optional nested select already in rule via _project_field_value
        if select:
            if matches:
                projected[str(field_name)] = data_leaf(
                    _take_from_element(matches[0], rule)
                )
            else:
                projected[str(field_name)] = data_leaf("")
        else:
            projected[str(field_name)] = _project_field_value(root, rule)

    return projected
