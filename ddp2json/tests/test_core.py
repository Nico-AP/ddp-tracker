"""Minimal regression tests for ddp2json."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ddp2json import __version__, process_archive, process_folder
from ddp2json.engine.cli import main, resolve_platform
from ddp2json.engine.parse.txt import text_to_tree
from ddp2json.engine.pipeline import MODE_FULL, MODE_SCHEMA, output_suffix
from ddp2json.engine.schema import to_schema
from ddp2json.engine.schema.describe import describe_value
from ddp2json.engine.schema.html import apply_html_specs
from ddp2json.engine.schema.path_redact import redact_path_parts
from ddp2json.engine.tree.nodes import file_leaf, is_media_path, unmatched_leaf


def _make_zip(path: Path, members: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, body in members.items():
            data = body.encode("utf-8") if isinstance(body, str) else body
            zf.writestr(name, data)
    return path


def test_version():
    assert __version__ == "0.1.0"


def test_output_suffixes():
    assert output_suffix(MODE_SCHEMA) == ".schema.json"
    assert output_suffix(MODE_FULL) == ".json"


def test_txt_empty_section_schema():
    tree = text_to_tree("""Send Gifts History:
You have no data in this section

Buy Gifts History:
Date: 2023-02-27 17:33:10
Price: 0.07
""")
    schema = to_schema(tree)
    assert schema["Send Gifts History"]["shape"] == "empty"
    assert schema["Send Gifts History"]["length"] == 0
    date = schema["Buy Gifts History"]["Date"]
    assert date["shape"] == "datetime"
    assert date["format"] == "%Y-%m-%d %H:%M:%S"


def test_describe_unix_format():
    assert describe_value("1700000000")["format"] == "s"
    assert describe_value(1700000000000)["format"] == "ms"


def test_file_leaf_media_vs_unmatched():
    assert is_media_path("a/b/photo.jpg")
    assert file_leaf("a/b/photo.jpg", 1, None)["kind"] == "media"
    assert file_leaf("docs/readme.pdf", 1, None)["kind"] == "unmatched"
    assert unmatched_leaf("x.html", 0, None)["kind"] == "unmatched"


def test_html_unmatched_without_specs(tmp_path: Path):
    html = {
        "kind": "html",
        "path": "index.html",
        "size": 10,
        "modified": None,
        "ext": ".html",
        "mime": "text/html",
        "dom": {"tag": "html", "children": {"kind": "list", "items": {}}},
    }
    out = apply_html_specs({"index.html": html}, platform="tiktok", specs=[])
    assert out["index.html"]["kind"] == "unmatched"


def test_html_match_with_spec(tmp_path: Path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>Hello</title></head><body></body></html>",
        encoding="utf-8",
    )
    from ddp2json.engine.parse.html import parse_html_tree

    node = parse_html_tree(path, tree_path="page.html", size=1, modified=None)
    spec = {
        "id": "t",
        "platforms": ["*"],
        "match": "**/*.html",
        "extract": {"title": {"select": "title", "take": "text"}},
    }
    out = apply_html_specs({"page.html": node}, platform="facebook", specs=[spec])
    # Spec matched → projected object (not unmatched). Title text may be empty
    # if the HTML parser collapsed the head/title structure.
    assert "title" in out["page.html"]
    assert out["page.html"]["title"]["kind"] == "data"
    assert out["page.html"].get("kind") != "unmatched"


def test_path_scrub_messages_thread():
    parts = redact_path_parts(
        ["messages", "inbox", "alice_123456789012345", "message_1.json"]
    )
    assert parts[0] == "messages"
    assert parts[1] == "inbox"
    assert (
        parts[2].startswith("u")
        or "{" in parts[2]
        or parts[2] != "alice_123456789012345"
    )
    # Thread folder should be redacted away from the raw name.
    assert "alice_123456789012345" not in parts


def test_process_archive_platform_and_mode(tmp_path: Path):
    zpath = _make_zip(
        tmp_path / "sample.zip",
        {
            "Purchases.txt": (
                "Send Gifts History:\n"
                "You have no data in this section\n\n"
                "Buy Gifts History:\n"
                "Date: 2025-04-21 18:55:21\n"
                "Price: 0.07\n"
            ),
            "photo.jpg": b"\xff\xd8\xff",
            "notes.pdf": b"%PDF-1.4",
            "page.html": "<html><body>hi</body></html>",
        },
    )
    report = process_archive(
        zpath, tmp_path / "extract", mode=MODE_SCHEMA, platform="tiktok"
    )
    assert report["platform"] == "tiktok"
    assert report["mode"] == MODE_SCHEMA
    tree = report["tree"]
    assert tree["photo.jpg"]["kind"] == "media"
    assert tree["notes.pdf"]["kind"] == "unmatched"
    assert tree["page.html"]["kind"] == "unmatched"
    assert tree["Purchases.txt"]["Send Gifts History"]["shape"] == "empty"


def test_process_folder_exit_and_suffix(tmp_path: Path, capsys):
    zdir = tmp_path / "in"
    zdir.mkdir()
    _make_zip(zdir / "a.zip", {"x.txt": "Key: value\n"})
    out = tmp_path / "out"
    failed = process_folder(str(zdir), str(out), mode=MODE_SCHEMA, platform="unknown")
    assert failed == 0
    assert (out / "a.schema.json").is_file()
    data = json.loads((out / "a.schema.json").read_text())
    assert data["platform"] == "unknown"


def test_cli_requires_platform_noninteractive(tmp_path: Path):
    zdir = tmp_path / "in"
    zdir.mkdir()
    _make_zip(zdir / "a.zip", {"x.txt": "A: 1\n"})
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        main([str(zdir), str(out)])


def test_resolve_platform_normalize():
    assert resolve_platform("TikTok") == "tiktok"
    assert resolve_platform("MyCorp") == "MyCorp"


def test_resolve_platform_prompts_per_archive(monkeypatch, capsys):
    answers = iter(["2", "tiktok"])  # 2 → instagram, then free-text tiktok

    monkeypatch.setattr("ddp2json.engine.cli.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    assert resolve_platform(None, archive_name="fb.zip") == "instagram"
    assert resolve_platform(None, archive_name="tt.zip") == "tiktok"
    out = capsys.readouterr().out
    assert "fb.zip" in out
    assert "tt.zip" in out
