"""Node paths as RFC 6901 JSON Pointer strings.

Spec: section 2.3 *Paths*. The root is ``""``; every folder/file entry and every object key adds
``/`` + name (``~`` → ``~0``, ``/`` → ``~1``). ``[]`` is the one reserved segment: the unified
item node of an array.
"""

import re

from ddp_parser.errors import InvalidPathError

ROOT = ""
ITEMS = "[]"

# A valid path: "" or any number of "/" + name, where "~" only appears as "~0" or "~1".
POINTER_PATTERN = r"^(/([^~/]|~[01])*)*$"

_BAD_ESCAPE = re.compile(r"~(?![01])")


def escape(name: str) -> str:
    return name.replace("~", "~0").replace("/", "~1")


def unescape(token: str) -> str:
    if _BAD_ESCAPE.search(token):
        msg = f"invalid escape sequence in {token!r}"
        raise InvalidPathError(msg)
    return token.replace("~1", "/").replace("~0", "~")


def join(parent: str, name: str) -> str:
    """Path of child ``name`` below ``parent`` (use ``ITEMS`` for an array's item node)."""
    return f"{parent}/{escape(name)}"


def split(path: str) -> list[str]:
    """Unescaped segments of ``path``; ``[]`` for the root."""
    if path == ROOT:
        return []
    if not path.startswith("/"):
        msg = f"path must be empty or start with '/': {path!r}"
        raise InvalidPathError(msg)
    return [unescape(token) for token in path[1:].split("/")]
