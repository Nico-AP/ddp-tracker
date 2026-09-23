"""Shared path / filename helpers for DDP zip entries."""

import os
import unicodedata


def fix_zip_name(name: str) -> str:
    """Repair filenames mangled by zipfile's CP437 fallback decoding.

    zipfile decodes entry names without the UTF-8 flag as CP437 (per the ZIP
    spec), but many archives actually store UTF-8 names. That turns e.g.
    "Kanäle" into "Kana<garbage>le". Re-encoding as CP437 and decoding as
    UTF-8 reverses it; we only keep the result if the round-trip succeeds.
    """
    try:
        repaired = name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = name
    return unicodedata.normalize("NFC", repaired)


def is_appledouble(path: str) -> bool:
    """True for macOS AppleDouble junk (._filename)."""
    return os.path.basename(path).startswith("._")


def is_real_csv(path: str) -> bool:
    """Skip AppleDouble junk; keep only true .csv entries."""
    return path.lower().endswith(".csv") and not is_appledouble(path)


def is_real_json(path: str) -> bool:
    """Skip AppleDouble junk; keep only true .json entries."""
    return path.lower().endswith(".json") and not is_appledouble(path)


def is_real_html(path: str) -> bool:
    """Skip AppleDouble junk; keep only true .html / .htm entries."""
    lower = path.lower()
    return lower.endswith((".html", ".htm")) and not is_appledouble(path)


def is_real_txt(path: str) -> bool:
    """Skip AppleDouble junk; keep only true .txt entries."""
    return path.lower().endswith(".txt") and not is_appledouble(path)
