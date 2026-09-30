"""Orchestration of the pipeline steps (source → plan → classify → parse → observe → build →
normalize → assemble).

The only module that knows the whole flow; every other module does one step and does not know
what runs before or after it.
"""

import zipfile
import zlib
from datetime import UTC, datetime
from importlib.metadata import version
from io import BytesIO
from pathlib import PurePosixPath
from typing import TypedDict

from ddp_parser.errors import LimitExceededError, ParseError
from ddp_parser.model import (
    ContainerNode,
    Document,
    FileNode,
    FilesystemNode,
    FolderNode,
    MediaNode,
    MimeSource,
    ParseWarning,
    Source,
    UnmatchedNode,
    UnmatchedReason,
)
from ddp_parser.normalize import normalize, rename_warnings, wrapper_warning
from ddp_parser.options import Options
from ddp_parser.parsers import Parsed, Parser, parser_for
from ddp_parser.schematize import NodeBuilder, data_fields
from ddp_parser.source import (
    Entry,
    InputData,
    PlannedFile,
    PlannedFolder,
    ReadBudget,
    open_input,
    plan,
    read_zip,
    unwrap,
)
from ddp_parser.source.mime import detect_mime, is_media, is_zip

# What reading a zip member can raise besides our own errors: corrupt data or checksum,
# encryption (RuntimeError), unsupported compression such as Deflate64 (NotImplementedError).
_ZIP_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError)
_ZIP_MIME = ("application/zip", MimeSource.MAGIC)


class _Meta(TypedDict):
    """Fields every file-like node shares (spec 2 and 4.1)."""

    name: str
    path: str
    size_bytes: int
    modified: datetime | None
    ext: str | None
    mime: str | None
    mime_source: MimeSource | None


def parse(data: InputData, options: Options | None = None, *, name: str | None = None) -> Document:
    """Schematize a DDP: a zip (path, bytes or binary stream) or a single file.

    ``name`` is the input's file name when it cannot be taken from a path or stream; for a
    single file it decides the parser (``posts.json``). Raises ``ParseError`` if the input
    looks like a zip but cannot be opened as one.
    """
    run = _Run(options or Options())
    source = open_input(data, name=name)
    try:
        if source.is_zip:
            try:
                archive = zipfile.ZipFile(source.stream)
            except _ZIP_ERRORS as exc:
                raise ParseError(str(exc)) from exc
            root: FilesystemNode = run.container(
                archive, name=source.name, path="", size=source.size, depth=0
            )
        else:
            entry = Entry(
                parts=(source.name or "",), size=source.size, modified=None, open=source.open
            )
            root = run.file(PlannedFile(name=source.name or "", path="", entries=[entry]), depth=0)
    finally:
        source.close()
    normalized = normalize(root, run.options)
    return Document(
        parser_version=version("ddp-parser"),
        created_at=datetime.now(UTC),
        source=Source(source.name, source.size, source.sha256),
        options=run.options.to_dict(),
        warnings=rename_warnings(run.warnings, normalized.renames),
        root=normalized.root,
    )


class _Run:
    """State of one ``parse`` call: options, the shared read budget, collected warnings."""

    def __init__(self, options: Options) -> None:
        self.options = options
        self.budget = ReadBudget(options)
        self.warnings: list[ParseWarning] = []

    # --- containers and folders --------------------------------------------------------------

    def container(
        self,
        archive: zipfile.ZipFile,
        *,
        name: str | None,
        path: str,
        size: int,
        depth: int,
        entry: Entry | None = None,
    ) -> ContainerNode:
        entries, unwrapped = unwrap(read_zip(archive, self.options, self.warnings, path=path), name)
        if unwrapped:
            self.warnings.append(wrapper_warning(path))
        tree = plan(entries, self.options, name=name, path=path)
        return ContainerNode(
            name=name,
            path=path,
            size_bytes=size,
            modified=entry.modified if entry else None,
            ext=_ext(name),
            mime=_ZIP_MIME[0],
            mime_source=_ZIP_MIME[1],
            children=self.children(tree, depth),
        )

    def folder(self, folder: PlannedFolder, depth: int) -> FolderNode:
        return FolderNode(
            name=folder.name,
            path=folder.path,
            modified=folder.modified,
            folders=folder.collapsed,
            children=self.children(folder, depth),
        )

    def children(self, folder: PlannedFolder, depth: int) -> tuple[FilesystemNode, ...]:
        nodes: list[FilesystemNode] = [
            self.folder(child, depth) for child in folder.folders.values()
        ]
        nodes += [self.file(planned, depth) for planned in folder.files]
        return tuple(sorted(nodes, key=lambda node: node.name or ""))

    # --- files -------------------------------------------------------------------------------

    def file(self, planned: PlannedFile, depth: int) -> FilesystemNode:
        first = planned.entries[0]
        if first.ignored:
            return self.unmatched(planned, UnmatchedReason.IGNORED)
        if is_zip(first.name):
            return self.nested_zip(planned, first, depth)
        parser = parser_for(first.name)
        if parser is not None:
            return self.parsed(planned, parser)
        try:
            mime, mime_source = detect_mime(planned.name, first.header())
        except _ZIP_ERRORS as exc:
            return self.unmatched(planned, UnmatchedReason.PARSE_ERROR, str(exc))
        if is_media(mime):
            return MediaNode(**self.meta(planned, mime, mime_source), files=_files(planned))
        return self.unmatched(
            planned, UnmatchedReason.UNSUPPORTED_TYPE, mime=mime, mime_source=mime_source
        )

    def nested_zip(self, planned: PlannedFile, entry: Entry, depth: int) -> FilesystemNode:
        if depth + 1 > self.options.max_depth:
            self.warnings.append(
                ParseWarning(code="max_depth", message="nested zip not opened", path=planned.path)
            )
            return self.unmatched(
                planned, UnmatchedReason.TOO_LARGE, "nested deeper than max_depth"
            )
        try:
            archive = zipfile.ZipFile(BytesIO(self.budget.read(entry)))
            return self.container(
                archive,
                name=planned.name,
                path=planned.path,
                size=entry.size,
                depth=depth + 1,
                entry=entry,
            )
        except LimitExceededError as exc:
            return self.unmatched(planned, UnmatchedReason.TOO_LARGE, str(exc))
        except _ZIP_ERRORS as exc:
            return self.unmatched(planned, UnmatchedReason.PARSE_ERROR, str(exc))

    def parsed(self, planned: PlannedFile, parser: Parser) -> FilesystemNode:
        """Parse every member into one builder; failed members are left out of the group."""
        builder = NodeBuilder(planned.name, planned.path, max_samples=self._max_samples)
        first: tuple[Parsed, bytes] | None = None
        failures: list[tuple[UnmatchedReason, str]] = []
        for entry in planned.entries:
            try:
                data = self.budget.read(entry)
                parsed = parser(data)
                if parsed.items is not None:
                    builder.observe_array(parsed.items)
                else:
                    builder.observe(parsed.value)
            except LimitExceededError as exc:
                failures.append((UnmatchedReason.TOO_LARGE, str(exc)))
            except (ParseError, *_ZIP_ERRORS) as exc:
                failures.append((UnmatchedReason.PARSE_ERROR, str(exc)))
            else:
                first = first or (parsed, data)
        if first is None:
            return self.unmatched(planned, *failures[0])
        if failures:
            reasons = ", ".join(sorted({reason.value for reason, _ in failures}))
            self.warnings.append(
                ParseWarning(
                    code="group_member_failed",
                    message=f"{len(failures)} of {len(planned.entries)} files left out ({reasons}): {failures[0][1]}",
                    path=planned.path,
                )
            )
        parsed, data = first
        mime, mime_source = detect_mime(planned.name, data[:262])
        return FileNode(
            **self.meta(planned, mime, mime_source),
            encoding=parsed.encoding,
            parser=parsed.parser,
            csv=parsed.csv,
            wrapper=parsed.wrapper,
            files=len(planned.entries) - len(failures) if planned.is_group else None,
            **data_fields(builder.build(self.options, self.warnings)),
        )

    def unmatched(
        self,
        planned: PlannedFile,
        reason: UnmatchedReason,
        error: str | None = None,
        *,
        mime: str | None = None,
        mime_source: MimeSource | None = None,
    ) -> UnmatchedNode:
        return UnmatchedNode(
            **self.meta(planned, mime, mime_source),
            reason=reason,
            error=error,
            files=_files(planned),
        )

    def meta(self, planned: PlannedFile, mime: str | None, mime_source: MimeSource | None) -> _Meta:
        """Common node fields. For a group: total size, newest modification time (spec 4.1)."""
        stamps = [entry.modified for entry in planned.entries if entry.modified]
        return _Meta(
            name=planned.name,
            path=planned.path,
            size_bytes=sum(entry.size for entry in planned.entries),
            modified=max(stamps) if stamps else None,
            ext=_ext(planned.name),
            mime=mime,
            mime_source=mime_source,
        )

    @property
    def _max_samples(self) -> int:
        return self.options.max_samples if self.options.samples else 0


def _files(planned: PlannedFile) -> int | None:
    return len(planned.entries) if planned.is_group else None


def _ext(name: str | None) -> str | None:
    return (PurePosixPath(name).suffix.lower() or None) if name else None
