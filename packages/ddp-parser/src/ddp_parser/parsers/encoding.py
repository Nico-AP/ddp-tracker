"""Text encoding detection: byte-order mark, then UTF-8, then cp1252.

Platform exports are almost always UTF-8; the rare legacy file is typically a Windows/Excel
export in cp1252. A fixed fallback is predictable, which matters more for schemas than a
statistical guess (charset-normalizer misread short and long Western samples alike as
cp1250/cp1257). Undefined cp1252 bytes are replaced rather than failing.

Encoding names are Python's canonical codec names (``utf-8``, ``utf-8-sig``, ``utf-16-le``,
``cp1252`` …), as the spec's ``encoding`` field expects.
"""

import codecs

_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32"),  # before UTF-16: its BOM starts with UTF-16 LE's
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def decode(data: bytes) -> tuple[str, str]:
    """Return ``(text, encoding)``."""
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return data.decode(encoding), _bom_name(bom, encoding)
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    return data.decode("cp1252", errors="replace"), "cp1252"


def _bom_name(bom: bytes, encoding: str) -> str:
    """Report the byte order a BOM implies (``utf-16-le``), which is more useful than ``utf-16``."""
    if encoding == "utf-8-sig":
        return encoding
    return f"{encoding}-{'le' if bom.startswith(b'\xff\xfe') else 'be'}"
