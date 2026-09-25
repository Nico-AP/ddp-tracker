"""Iterate over a schema tree: every node below (and including) a root, in document order."""

from collections.abc import Iterator

from ddp_parser.model.nodes import ContainerNode, DataNode, FileNode, FolderNode, Node


def children(node: Node) -> list[Node]:
    """A node's direct children: folder / container entries, or the properties and the item
    node of parsed content.
    """
    match node:
        case ContainerNode() | FolderNode():
            return list(node.children)
        case FileNode() | DataNode():
            below: list[Node] = list((node.properties or {}).values())
            if node.items is not None:
                below.append(node.items)
            return below
        case _:
            return []


def walk(node: Node) -> Iterator[Node]:
    """``node`` and all its descendants, depth-first in document order."""
    yield node
    for child in children(node):
        yield from walk(child)
