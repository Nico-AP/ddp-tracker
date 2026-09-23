"""Archive orchestration: extract → build tree → optional schema redact."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import zipfile

from .report.summary import summarize_entries
from .schema import to_schema
from .schema.html import apply_html_specs, default_specs_dir
from .tree import build_tree, format_modified
from .tree.paths import is_appledouble

# Output modes
MODE_SCHEMA = "schema"  # fully redacted descriptors (default)
MODE_SCHEMA_ENUMS = "schema_enums"  # redacted paths + safe unique values
MODE_SCHEMA_FULL = "schema_full"  # unredacted paths + all enum values
MODE_FULL = "full"  # unredacted content tree

_MODE_SUFFIX = {
    MODE_SCHEMA: ".schema.json",
    MODE_SCHEMA_ENUMS: ".schema-enums.json",
    MODE_SCHEMA_FULL: ".schema-full.json",
    MODE_FULL: ".json",
}

# schema modes → (values_mode, redact_paths)
_SCHEMA_OPTIONS = {
    MODE_SCHEMA: ("none", True),
    MODE_SCHEMA_ENUMS: ("safe", True),
    MODE_SCHEMA_FULL: ("all", False),
}

KNOWN_PLATFORMS = (
    "facebook",
    "instagram",
    "tiktok",
    "google",
    "x",
    "netflix",
    "spotify",
    "airbnb",
    "uber",
    "unknown",
)


def output_suffix(mode: str) -> str:
    """Filename suffix for a report mode."""
    try:
        return _MODE_SUFFIX[mode]
    except KeyError as exc:
        raise ValueError(f"Unknown mode: {mode!r}") from exc


def normalize_platform(platform: str) -> str:
    """Normalize a platform label (strip; lowercase known names)."""
    text = (platform or "").strip()
    if not text:
        raise ValueError("platform must be a non-empty string")
    lower = text.lower()
    if lower in KNOWN_PLATFORMS:
        return lower
    return text


def _entry_meta(info) -> dict:
    """Lightweight file/dir meta used only for the summary (not written out)."""
    return {
        "path": info.filename,
        "is_dir": info.filename.endswith("/"),
        "size": info.file_size,
        "modified": format_modified(info.date_time) or "1980-00-00 00:00:00",
    }


def process_archive(
    zip_path: Path,
    tmp_root: Path,
    mode: str = MODE_SCHEMA,
    html_specs_dir: Path | None = None,
    *,
    platform: str,
) -> dict:
    """Extract one ZIP and return its report (archive meta + content tree).

    Modes:
      - ``schema`` (default): descriptors only — no enum ``values``; paths scrubbed
      - ``schema_enums``: descriptors + safe non-PII unique values; paths scrubbed
      - ``schema_full``: descriptors + all unique values; paths kept
      - ``full``: unredacted content tree (original paths and raw values)

    ``platform`` labels the archive for HTML spec matching (and report meta).
    Known values: facebook / instagram / tiktok / google / x / netflix /
    spotify / airbnb / uber / unknown; any other non-empty string is kept as a
    custom label. Registry aliases (e.g. youtube → google) live in
    ddp_registry/platforms.json.

    ``build_tree`` is structure-only (JSON/CSV/HTML DOM/TXT). Schema modes run
    ``apply_html_specs`` (project or mark unmatched) then ``to_schema``.
    ``--full`` skips both and keeps the DOM.
    """
    if mode not in _MODE_SUFFIX:
        raise ValueError(f"Unknown mode: {mode!r}")

    platform = normalize_platform(platform)

    dest = tmp_root / zip_path.stem
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        info_list = zf.infolist()
        zf.extractall(dest)

    entries = [
        _entry_meta(info) for info in info_list if not is_appledouble(info.filename)
    ]

    print("  Building content tree...")
    tree = build_tree(dest, info_list)
    if mode in _SCHEMA_OPTIONS:
        specs_dir = (
            html_specs_dir if html_specs_dir is not None else default_specs_dir()
        )
        print("  Applying HTML specs (unmatched → unmatched leaf)...")
        tree = apply_html_specs(tree, platform=platform, specs_dir=specs_dir)
        values_mode, redact_paths = _SCHEMA_OPTIONS[mode]
        labels = {
            "none": "schema descriptors...",
            "safe": "schema descriptors (safe enums)...",
            "all": "schema descriptors (all enums, no path redact)...",
        }
        print(f"  Redacting to {labels[values_mode]}")
        tree = to_schema(tree, values_mode=values_mode, redact_paths=redact_paths)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "archive": zip_path.name,
        "platform": platform,
        "mode": mode,
        "summary": summarize_entries(entries),
        "tree": tree,
    }
    return report
