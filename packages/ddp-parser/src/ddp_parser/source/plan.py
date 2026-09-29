"""Step 2: arrange a container's entries into a folder tree.

Folders that exist only implicitly (``a/b.json`` without an ``a/`` entry) are created. Look-alike
sibling folders are collapsed into one ``{*}`` folder (spec 3.5), then numbered files are grouped
(spec 3.4) and paths assigned. The tree holds entries only; nothing has been read yet.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatchcase

from ddp_parser.model.paths import join
from ddp_parser.options import Options
from ddp_parser.privacy.path_redact import join_redacted
from ddp_parser.source.entry import Entry
from ddp_parser.source.grouping import group_names, mask_name, pattern_of

COLLAPSED = "{*}"


@dataclass(slots=True, kw_only=True)
class PlannedFile:
    """One file node to build: a single entry, or several (``name`` is then their pattern, or
    the shared name across collapsed folders).
    """

    name: str
    path: str = ""
    entries: list[Entry]

    @property
    def is_group(self) -> bool:
        return len(self.entries) > 1


@dataclass(slots=True, kw_only=True)
class PlannedFolder:
    name: str | None
    path: str = ""
    modified: datetime | None = None
    collapsed: int | None = None  # how many sibling folders were merged into this one
    folders: dict[str, "PlannedFolder"] = field(default_factory=dict)  # key: path segment
    loose: list[Entry] = field(default_factory=list)  # files before grouping
    files: list[PlannedFile] = field(default_factory=list)

    def folder(self, parts: tuple[str, ...]) -> "PlannedFolder":
        """The descendant folder at ``parts``, created on the way if needed."""
        node = self
        for part in parts:
            node = node.folders.setdefault(part, PlannedFolder(name=part))
        return node


def plan(
    entries: list[Entry], options: Options, *, name: str | None = None, path: str = ""
) -> PlannedFolder:
    """The folder tree of one container; ``path`` is the container's own node path."""
    root = PlannedFolder(name=name)
    for entry in entries:
        if entry.is_dir:
            root.folder(entry.parts).modified = entry.modified
        else:
            root.folder(entry.parts[:-1]).loose.append(entry)
    _finish(root, path, options)
    return root


def _finish(folder: PlannedFolder, path: str, options: Options) -> None:
    folder.path = path
    if folder.folders and _should_collapse(folder, options):
        folder.folders = {COLLAPSED: _collapse(list(folder.folders.values()))}
    for segment, child in folder.folders.items():
        child_path = join_redacted(path, segment) if options.redact_paths else join(path, segment)
        _finish(child, child_path, options)
    folder.files = _group(folder.path, folder.loose, options)


def _should_collapse(folder: PlannedFolder, options: Options) -> bool:
    if _matches(folder.path, options.keep_folders):
        return False
    if _matches(folder.path, options.collapse_folders):
        return True
    return not folder.loose and len(folder.folders) >= 2 and _look_alike(folder.folders.values())  # noqa: PLR2004 - two is the smallest set of siblings


def _look_alike(folders: Iterable[PlannedFolder]) -> bool:
    """True if, on average, at least half of each folder's child names (digits as ``{n}``) are
    shared by more than half of the folders.
    """
    signatures = [_signature(folder) for folder in folders]
    if not all(signatures):
        return False
    counts = Counter(name for signature in signatures for name in signature)
    common = {name for name, count in counts.items() if count * 2 > len(signatures)}
    shares = [len(signature & common) / len(signature) for signature in signatures]
    return sum(shares) / len(shares) >= 0.5  # noqa: PLR2004 - "at least half"


def _signature(folder: PlannedFolder) -> set[str]:
    return {pattern_of(entry.name) for entry in folder.loose} | {
        pattern_of(name) + "/" for name in folder.folders
    }


def _collapse(folders: list[PlannedFolder]) -> PlannedFolder:
    masks = Counter(mask_name(folder.name or "") for folder in folders)
    name = min(masks, key=lambda mask: (-masks[mask], mask))  # most common, ties by name
    merged = _merge(folders, name)
    merged.collapsed = len(folders)
    return merged


def _merge(folders: list[PlannedFolder], name: str | None) -> PlannedFolder:
    """One folder holding all files of ``folders``; same-named subfolders merge recursively."""
    merged = PlannedFolder(name=name)
    by_name: dict[str, list[PlannedFolder]] = {}
    for folder in folders:
        merged.loose.extend(folder.loose)
        for child_name, child in folder.folders.items():
            by_name.setdefault(child_name, []).append(child)
    for child_name, children in by_name.items():
        merged.folders[child_name] = (
            children[0] if len(children) == 1 else _merge(children, child_name)
        )
    if len(folders) == 1:
        merged.modified = folders[0].modified
    return merged


def _matches(path: str, rules: tuple[str, ...]) -> bool:
    segments = path.split("/")
    for rule in rules:
        pattern = rule.split("/")
        if len(pattern) == len(segments) and all(map(fnmatchcase, segments, pattern)):
            return True
    return False


def _group(folder_path: str, entries: list[Entry], options: Options) -> list[PlannedFile]:
    patterns = group_names({entry.name for entry in entries})
    planned: dict[str, PlannedFile] = {}
    for entry in entries:
        name = patterns.get(entry.name, entry.name)
        if name in planned:
            planned[name].entries.append(entry)
        else:
            file_path = (
                join_redacted(folder_path, name)
                if options.redact_paths
                else join(folder_path, name)
            )
            planned[name] = PlannedFile(name=name, path=file_path, entries=[entry])
    return list(planned.values())
