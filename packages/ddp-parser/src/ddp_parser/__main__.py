"""Developer CLI: ``python -m ddp_parser export.zip > schema.json``."""

import argparse
import sys
from pathlib import Path

from ddp_parser import Options, ParseError, parse, to_json


def main(argv: list[str] | None = None) -> int:
    arguments = argparse.ArgumentParser(
        prog="python -m ddp_parser", description="Print the schema document of a DDP as JSON."
    )
    arguments.add_argument("input", type=Path, help="a zip archive or a single file")
    arguments.add_argument("--samples", action="store_true", help="include masked sample values")
    arguments.add_argument(
        "--collapse",
        action="append",
        default=[],
        metavar="PATH",
        help="collapse this folder's subfolders",
    )
    arguments.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="PATH",
        help="never collapse this folder's subfolders",
    )
    args = arguments.parse_args(argv)
    options = Options(
        samples=args.samples, collapse_folders=tuple(args.collapse), keep_folders=tuple(args.keep)
    )
    try:
        document = parse(args.input, options)
    except (OSError, ParseError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    sys.stdout.write(to_json(document) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
