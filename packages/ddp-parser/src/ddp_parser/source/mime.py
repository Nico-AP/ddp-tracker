"""What is this file? MIME type and whether it is media (spec 4.1).

The MIME type comes from the file's *magic bytes* (a known signature at the start of the
content, e.g. ``\\x89PNG`` or ``PK\\x03\\x04``) when one matches, else from the extension;
``mime_source`` records which.
"""

import mimetypes

import filetype

from ddp_parser.model import MimeSource

_MEDIA_PREFIXES = ("image/", "video/", "audio/")


def detect_mime(name: str, header: bytes) -> tuple[str | None, MimeSource | None]:
    magic = filetype.guess_mime(header)
    if magic is not None:
        return magic, MimeSource.MAGIC
    guessed, _ = mimetypes.guess_type(name, strict=False)
    return (guessed, MimeSource.EXTENSION) if guessed else (None, None)


def is_media(mime: str | None) -> bool:
    return mime is not None and mime.startswith(_MEDIA_PREFIXES)


def is_zip(name: str) -> bool:
    """Nested containers are recognised by extension: Office files, ``.jar`` or ``.epub`` share
    the zip signature but are not folders.
    """
    return name.lower().endswith(".zip")
