"""CLI: argparse and batch ZIP processing."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .._version import __version__
from .pipeline import (
    KNOWN_PLATFORMS,
    MODE_FULL,
    MODE_SCHEMA,
    MODE_SCHEMA_ENUMS,
    MODE_SCHEMA_FULL,
    normalize_platform,
    output_suffix,
    process_archive,
)
from .schema.html import default_specs_dir


def _prompt_platform(archive_name: str | None = None) -> str:
    """Interactive platform selection (known list or custom string)."""
    if archive_name:
        print(f"Select platform for {archive_name}:")
    else:
        print("Select platform:")
    for i, name in enumerate(KNOWN_PLATFORMS, start=1):
        print(f"  {i}) {name}")
    print(f"  {len(KNOWN_PLATFORMS) + 1}) other (type a custom label)")
    while True:
        choice = input("Platform [1-{}]: ".format(len(KNOWN_PLATFORMS) + 1)).strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(KNOWN_PLATFORMS):
                return KNOWN_PLATFORMS[idx - 1]
            if idx == len(KNOWN_PLATFORMS) + 1:
                custom = input("Custom platform label: ").strip()
                if custom:
                    return normalize_platform(custom)
                print("Label cannot be empty.")
                continue
        # Treat free text as an open input (known name or custom).
        if choice:
            try:
                return normalize_platform(choice)
            except ValueError:
                pass
        print("Enter a number from the list, a known name, or a custom label.")


def resolve_platform(
    platform: str | None,
    *,
    archive_name: str | None = None,
) -> str:
    """Resolve ``--platform``, or prompt per archive when stdin is a TTY."""
    if platform is not None and str(platform).strip():
        return normalize_platform(platform)
    if sys.stdin.isatty():
        return _prompt_platform(archive_name)
    raise SystemExit(
        "error: --platform is required in non-interactive mode "
        f"(one of {', '.join(KNOWN_PLATFORMS)}, or any custom label)"
    )


def process_zips(
    zip_files: list[Path],
    output_dir: Path,
    mode: str = MODE_SCHEMA,
    html_specs_dir: Path | None = None,
    *,
    platform: str | None = None,
) -> int:
    """Convert each ZIP and write one JSON report into ``output_dir``.

    When ``platform`` is set, every archive uses that label. When omitted,
    each archive is prompted for on a TTY (required flag otherwise).

    Returns the number of failed archives (0 on full success).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    failed = 0
    suffix = output_suffix(mode)
    specs_dir = html_specs_dir if html_specs_dir is not None else default_specs_dir()
    fixed_platform = (
        normalize_platform(platform)
        if platform is not None and str(platform).strip()
        else None
    )

    with tempfile.TemporaryDirectory(prefix="zip_analysis_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for zip_path in zip_files:
            try:
                archive_platform = (
                    fixed_platform
                    if fixed_platform is not None
                    else resolve_platform(None, archive_name=zip_path.name)
                )
                print(f"Extracting: {zip_path.name} (platform={archive_platform})")
                report = process_archive(
                    zip_path,
                    tmp_path,
                    mode=mode,
                    html_specs_dir=specs_dir,
                    platform=archive_platform,
                )
                output_file = output_dir / f"{zip_path.stem}{suffix}"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                written += 1

                s = report["summary"]
                print(
                    f"  → {s['file_count']} files, {s['dir_count']} dirs, "
                    f"{s['total_size_human']}"
                )
                print(f"  Saved: {output_file}")

            except SystemExit:
                raise
            except Exception as exc:
                failed += 1
                print(f"  ✗ Failed: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written} file(s) to {output_dir}")
    if failed:
        print(f"Failed: {failed} archive(s)", file=sys.stderr)
    return failed


def process_folder(
    folder: str,
    output_dir: str | None = None,
    mode: str = MODE_SCHEMA,
    html_specs_dir: Path | None = None,
    *,
    platform: str | None = None,
) -> int:
    """Find ``*.zip`` under ``folder`` and convert them (see ``process_zips``).

    Returns the number of failed archives (or ``1`` for invalid folder / no ZIPs).
    """
    folder_path = Path(folder).resolve()

    if not folder_path.is_dir():
        print(f"Error: '{folder}' is not a directory.", file=sys.stderr)
        return 1

    zip_files = sorted(folder_path.glob("*.zip"))
    if not zip_files:
        print("No ZIP files found.")
        return 1

    out = Path(output_dir).resolve() if output_dir else folder_path.parent / "output"
    return process_zips(
        zip_files,
        out,
        mode=mode,
        html_specs_dir=html_specs_dir,
        platform=platform,
    )


def main(argv: list[str] | None = None) -> None:
    """Parse CLI args and run ``process_folder``."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert DDP ZIP archives into JSON content trees. "
            "Default: fully redacted schema (type/shape only, no unique values)."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("folder", nargs="?", help="Folder containing .zip DDP archives")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Output directory (default: <folder>/../output)",
    )
    parser.add_argument(
        "--platform",
        default=None,
        metavar="NAME",
        help=(
            "Platform label applied to every archive "
            f"({'|'.join(KNOWN_PLATFORMS)}, or any custom string). "
            "If omitted on a TTY, you are prompted once per ZIP; "
            "required in non-interactive mode."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--enums",
        action="store_const",
        const=MODE_SCHEMA_ENUMS,
        dest="mode",
        help=(
            "Partially redacted schema: keep short non-PII unique values. "
            "Writes <stem>.schema-enums.json"
        ),
    )
    mode_group.add_argument(
        "--schema-full",
        action="store_const",
        const=MODE_SCHEMA_FULL,
        dest="mode",
        help=(
            "Unredacted schema: keep all unique values and original paths. "
            "Writes <stem>.schema-full.json"
        ),
    )
    mode_group.add_argument(
        "--full",
        action="store_const",
        const=MODE_FULL,
        dest="mode",
        help="Unredacted content tree. Writes <stem>.json",
    )
    parser.add_argument(
        "--html-specs",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Directory of HTML projection JSON specs (schema modes only). "
            "Default: package policy/html. Unmatched HTML → unmatched leaf."
        ),
    )
    parser.set_defaults(mode=MODE_SCHEMA)
    args = parser.parse_args(argv)

    if not args.folder:
        parser.error("folder is required")

    failed = process_folder(
        args.folder,
        args.output_dir,
        mode=args.mode,
        html_specs_dir=args.html_specs,
        platform=args.platform,
    )
    if failed:
        sys.exit(1)
