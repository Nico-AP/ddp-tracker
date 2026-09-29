"""Steps 1-3: open the input, turn containers into planned folder trees, classify files.

An input is a path (streamed from disk, never loaded whole), bytes, or a binary file object.
"""

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from ddp_parser.source.entry import Entry, ReadBudget
from ddp_parser.source.plan import PlannedFile, PlannedFolder, plan
from ddp_parser.source.unwrap import same_name, unwrap
from ddp_parser.source.zip import read_zip

type InputData = str | Path | bytes | IO[bytes]

_CHUNK = 1024 * 1024
# a local file header (every non-empty zip starts with one), an empty zip's end record
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")


@dataclass(frozen=True, slots=True)
class Input:
    name: str | None
    size: int
    sha256: str
    stream: IO[bytes]  # seekable, positioned at 0
    path: Path | None = None  # set when the input was given as a path (we own ``stream``)

    @property
    def is_zip(self) -> bool:
        """A zip by its end record, or by a zip signature at the start. The signature matters for
        a damaged archive: since Python 3.14 ``is_zipfile`` also checks the central directory,
        and a zip that can't be opened must still raise ``ParseError``, not become a file."""
        position = self.stream.tell()
        try:
            if zipfile.is_zipfile(self.stream):
                return True
            self.stream.seek(0)
            return self.stream.read(4) in _ZIP_SIGNATURES
        finally:
            self.stream.seek(position)

    def open(self) -> IO[bytes]:
        """A fresh stream over the whole input, for reading it as a single file."""
        if self.path is not None:
            return self.path.open("rb")
        self.stream.seek(0)
        return io.BytesIO(self.stream.read())

    def close(self) -> None:
        """Close the stream if ``open_input`` opened it; callers' own streams stay open."""
        if self.path is not None:
            self.stream.close()


def open_input(data: InputData, *, name: str | None = None) -> Input:
    """Wrap the input with its name, size and SHA-256. A path is opened as a file and read in
    chunks, never loaded whole; call ``Input.close()`` when done (the pipeline does).
    """
    if isinstance(data, str | Path):
        path = Path(data)
        return _measure(path.open("rb"), name or path.name, path)
    if isinstance(data, bytes):
        return _measure(io.BytesIO(data), name)
    return _measure(data, name or _stream_name(data))


def _measure(stream: IO[bytes], name: str | None, path: Path | None = None) -> Input:
    digest = hashlib.sha256()
    size = 0
    stream.seek(0)
    while chunk := stream.read(_CHUNK):
        digest.update(chunk)
        size += len(chunk)
    stream.seek(0)
    return Input(name=name, size=size, sha256=digest.hexdigest(), stream=stream, path=path)


def _stream_name(stream: IO[bytes]) -> str | None:
    name = getattr(stream, "name", None)
    return Path(name).name if isinstance(name, str) else None


__all__ = [
    "Entry",
    "Input",
    "InputData",
    "PlannedFile",
    "PlannedFolder",
    "ReadBudget",
    "open_input",
    "plan",
    "read_zip",
    "same_name",
    "unwrap",
]
