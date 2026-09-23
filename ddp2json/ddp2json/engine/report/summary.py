"""Archive-level summary stats for report wrappers."""

from pathlib import Path


def human_size(num_bytes: int) -> str:
    """Return a human-readable size string (B, KB, MB, GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def summarize_entries(entries: list[dict]) -> dict:
    """Compute file/dir counts, size, date range, and extension histogram.

    ``entries`` are lightweight dicts from the ZIP member list
    (``path``, ``is_dir``, ``size``, ``modified``)—not the content tree.
    """
    files = [e for e in entries if not e["is_dir"]]
    dirs = [e for e in entries if e["is_dir"]]
    total_size = sum(e["size"] for e in files)

    # ZIP format can't represent dates before 1980; treat that sentinel
    # value as "unknown" rather than a real timestamp.
    dates = [e["modified"] for e in files if e["modified"] != "1980-00-00 00:00:00"]
    oldest = min(dates) if dates else None
    newest = max(dates) if dates else None

    ext_counts: dict[str, int] = {}
    for e in files:
        ext = Path(e["path"]).suffix.lower() or "(no extension)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    return {
        "file_count": len(files),
        "dir_count": len(dirs),
        "total_size_bytes": total_size,
        "total_size_human": human_size(total_size),
        "oldest_modified": oldest,
        "newest_modified": newest,
        "extensions": dict(sorted(ext_counts.items(), key=lambda kv: -kv[1])),
    }
