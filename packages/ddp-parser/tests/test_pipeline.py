import io
import json
import tempfile
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import TestCase

from ddp_parser import Options, ParseError, parse, to_dict
from ddp_parser.__main__ import main
from ddp_parser.model import ContainerNode, FileNode, FolderNode, MediaNode, UnmatchedNode
from tests.test_parsers import LOGINS_CSV, PROFILE_JSON

WORKED_EXAMPLE = Path(__file__).parent / "fixtures" / "worked_example.json"
STAMP: tuple[int, int, int, int, int, int] = (2026, 9, 20, 14, 2, 10)
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def make_zip(
    members: dict[str, bytes], stamp: tuple[int, int, int, int, int, int] = STAMP
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=stamp), data)
    return buffer.getvalue()


def children(node) -> dict:
    return {child.name: child for child in node.children}


class WorkedExampleTests(TestCase):
    """``parse()`` on the spec's export.zip yields the spec's document (index.md §8)."""

    def setUp(self):
        self.data = make_zip({"logins.csv": LOGINS_CSV, "profile.json": PROFILE_JSON})
        self.expected = json.loads(WORKED_EXAMPLE.read_text(encoding="utf-8"))

    def assert_matches_spec(self, document):
        got, expected = to_dict(document), json.loads(json.dumps(self.expected))
        for data in (got, expected):
            del data["created_at"], data["source"]["sha256"]  # time- and platform-dependent
        self.assertEqual(got, expected)

    def test_from_bytes(self):
        self.assert_matches_spec(parse(self.data, name="export.zip"))

    def test_from_path_and_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.zip"
            path.write_bytes(self.data)
            self.assert_matches_spec(parse(path))
            with path.open("rb") as stream:
                self.assert_matches_spec(parse(stream))
                self.assertFalse(stream.closed)  # the caller's stream stays open


class SingleFileTests(TestCase):
    def test_json_file_is_the_root(self):
        root = parse(PROFILE_JSON, name="profile.json").root
        assert isinstance(root, FileNode)
        self.assertEqual(
            (root.name, root.path, root.parser, root.ext), ("profile.json", "", "json", ".json")
        )
        self.assertEqual(root.size_bytes, len(PROFILE_JSON))

    def test_path_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logins.csv"
            path.write_bytes(LOGINS_CSV)
            root = parse(path).root
        assert isinstance(root, FileNode)
        self.assertEqual((root.parser, root.name), ("csv", "logins.csv"))

    def test_unnamed_bytes_are_unsupported(self):
        root = parse(b"{}").root
        assert isinstance(root, UnmatchedNode)
        self.assertEqual(root.reason, "unsupported_type")


class FileKindTests(TestCase):
    def setUp(self):
        members = {
            "photo.jpg": PNG,  # wrong extension: magic wins
            "notes.pdf": b"%PDF-1.4 ...",
            "README": b"hello",
            "broken.json": b"{",
            "b.json": b"{}",
            "a.json": b"[]",
        }
        self.root = parse(make_zip(members), name="export.zip").root

    def test_children_sorted_by_name(self):
        names = list(children(self.root))
        self.assertEqual(names, sorted(names))

    def test_kinds(self):
        nodes = children(self.root)
        photo = nodes["photo.jpg"]
        assert isinstance(photo, MediaNode)
        self.assertEqual((photo.mime, photo.mime_source), ("image/png", "magic"))
        pdf, readme, broken = nodes["notes.pdf"], nodes["README"], nodes["broken.json"]
        assert isinstance(pdf, UnmatchedNode)
        assert isinstance(readme, UnmatchedNode)
        assert isinstance(broken, UnmatchedNode)
        self.assertEqual((pdf.reason, pdf.mime), ("unsupported_type", "application/pdf"))
        self.assertEqual((readme.reason, readme.mime, readme.ext), ("unsupported_type", None, None))
        self.assertEqual(broken.reason, "parse_error")
        self.assertIsNotNone(broken.error)
        self.assertIsInstance(nodes["a.json"], FileNode)

    def test_kept_junk_is_listed_as_ignored(self):
        root = parse(make_zip({".DS_Store": b"x"}), Options(keep_ignored=True), name="x.zip").root
        junk = children(root)[".DS_Store"]
        assert isinstance(junk, UnmatchedNode)
        self.assertEqual(junk.reason, "ignored")


class GroupTests(TestCase):
    def test_group_merges_files(self):
        members = {
            "message_1.json": b'{"text": "hi"}',
            "message_2.json": b'{"text": "yo", "photo": "a.jpg"}',
        }
        root = parse(make_zip(members), name="x.zip").root
        group = children(root)["message_{n}.json"]
        assert isinstance(group, FileNode)
        assert group.properties is not None
        self.assertEqual((group.path, group.files, group.stats.count), ("/message_{n}.json", 2, 2))
        self.assertEqual(group.size_bytes, sum(len(data) for data in members.values()))
        self.assertEqual(group.properties["photo"].stats.present, 1)

    def test_failed_member_is_left_out_with_a_warning(self):
        document = parse(
            make_zip({"m_1.json": b"{}", "m_2.json": b"{", "m_3.json": b"{}"}), name="x.zip"
        )
        group = children(document.root)["m_{n}.json"]
        assert isinstance(group, FileNode)
        self.assertEqual(group.files, 2)
        self.assertEqual([w.code for w in document.warnings], ["group_member_failed"])
        self.assertIn("1 of 3 files left out (parse_error)", document.warnings[0].message or "")

    def test_all_members_failing_make_one_unmatched_node(self):
        root = parse(make_zip({"m_1.json": b"{", "m_2.json": b"["}), name="x.zip").root
        group = children(root)["m_{n}.json"]
        assert isinstance(group, UnmatchedNode)
        self.assertEqual((group.reason, group.files), ("parse_error", 2))

    def test_media_group(self):
        root = parse(make_zip({"IMG_1.jpg": PNG, "IMG_2.jpg": PNG}), name="x.zip").root
        group = children(root)["IMG_{n}.jpg"]
        assert isinstance(group, MediaNode)
        self.assertEqual(group.files, 2)

    def test_path_redact_single_thread_folder(self):
        members = {
            "messages/inbox/alice_123456789012345/message_1.json": b'{"text": "hi"}',
        }
        root = parse(make_zip(members), name="x.zip").root
        inbox = children(children(root)["messages"])["inbox"]
        thread = next(iter(children(inbox).values()))
        self.assertNotIn("alice_123456789012345", thread.path)
        self.assertTrue(thread.path.startswith("/messages/inbox/u"))

    def test_collapsed_folders(self):
        members = {
            "messages/inbox/johndoe_1234/message_1.json": b'{"text": "hi"}',
            "messages/inbox/janedoe_5678/message_1.json": b'{"text": "yo"}',
            "messages/inbox/janedoe_5678/message_2.json": b'{"text": "hey"}',
        }
        root = parse(make_zip(members), name="x.zip").root
        inbox = children(children(root)["messages"])["inbox"]
        thread = children(inbox)["xs0"]
        assert isinstance(thread, FolderNode)
        self.assertEqual((thread.path, thread.folders), ("/messages/inbox/{*}", 2))
        messages = children(thread)["message_{n}.json"]
        assert isinstance(messages, FileNode)
        self.assertEqual(
            (messages.path, messages.files), ("/messages/inbox/{*}/message_{n}.json", 3)
        )


class ContainerTests(TestCase):
    def test_nested_zip(self):
        inner = make_zip({"a.json": b"{}"})
        root = parse(make_zip({"inner.zip": inner}), name="outer.zip").root
        nested = children(root)["inner.zip"]
        assert isinstance(nested, ContainerNode)
        self.assertEqual(
            (nested.path, nested.size_bytes, nested.mime),
            ("/inner.zip", len(inner), "application/zip"),
        )
        self.assertEqual(children(nested)["a.json"].path, "/inner.zip/a.json")

    def test_max_depth(self):
        innermost = make_zip({"a.json": b"{}"})
        data = make_zip({"one.zip": make_zip({"two.zip": innermost})})
        document = parse(data, Options(max_depth=1), name="x.zip")
        two = children(children(document.root)["one.zip"])["two.zip"]
        assert isinstance(two, UnmatchedNode)
        self.assertEqual(two.reason, "too_large")
        self.assertEqual(
            [(w.code, w.path) for w in document.warnings], [("max_depth", "/one.zip/two.zip")]
        )

    def test_nested_zip_over_the_size_limit(self):
        inner = make_zip({"a.json": b"{}"})
        root = parse(make_zip({"inner.zip": inner}), Options(max_entry_size=10), name="x.zip").root
        self.assertEqual(children(root)["inner.zip"].reason, "too_large")

    def test_broken_nested_zip(self):
        root = parse(make_zip({"inner.zip": b"not a zip"}), name="x.zip").root
        nested = children(root)["inner.zip"]
        assert isinstance(nested, UnmatchedNode)
        self.assertEqual(nested.reason, "parse_error")

    def test_size_limits(self):
        members = {"a.json": b"[1, 2, 3]", "b.json": b"[4]", "c.json": b"{}"}
        root = parse(
            make_zip(members), Options(max_entry_size=5, max_total_size=7), name="x.zip"
        ).root
        nodes = children(root)
        self.assertEqual(nodes["a.json"].reason, "too_large")
        self.assertIsInstance(nodes["b.json"], FileNode)
        self.assertIsInstance(nodes["c.json"], FileNode)
        members = {"a.json": b"[1]", "b.json": b"[2]", "c.json": b"[3]"}
        root = parse(make_zip(members), Options(max_total_size=6), name="x.zip").root
        self.assertEqual(children(root)["c.json"].reason, "too_large")

    def test_unsupported_compression_is_a_parse_error(self):
        data = bytearray(make_zip({"a.json": b"{}", "b.jpg": PNG}))
        for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
            start = 0
            while (start := data.find(signature, start)) != -1:
                data[start + offset] = 9  # Deflate64, which zipfile cannot read
                start += 4
        nodes = children(parse(bytes(data), name="x.zip").root)
        self.assertEqual(nodes["a.json"].reason, "parse_error")
        self.assertEqual(nodes["b.jpg"].reason, "parse_error")

    def test_unreadable_top_level_zip(self):
        data = make_zip({"a.json": b"{}"}).replace(b"PK\x01\x02", b"XX\x01\x02")
        with self.assertRaises(ParseError):
            parse(data, name="x.zip")

    def test_warnings_reach_the_document(self):
        document = parse(make_zip({"../evil.json": b"{}", "ok.json": b"{}"}), name="x.zip")
        self.assertEqual([w.code for w in document.warnings], ["unsafe_path"])

    def test_samples_option(self):
        root = parse(b'[{"n": 5}, {"n": 9}]', Options(samples=True), name="a.json").root
        assert isinstance(root, FileNode)
        assert root.items is not None
        assert root.items.properties is not None
        n = root.items.properties["n"]
        assert n.range is not None
        self.assertEqual((n.range.min, n.range.max), (5, 9))
        self.assertIsNotNone(n.samples)


class CliTests(TestCase):
    def test_prints_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.json"
            path.write_bytes(b'{"a": 1}')
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([str(path), "--samples", "--collapse", "/x", "--keep", "/y"])
        document = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(document["root"]["name"], "a.json")
        self.assertEqual(document["options"]["collapse_folders"], ["/x"])

    def test_missing_input(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["/does/not/exist.zip"])
        self.assertEqual(code, 1)
        self.assertIn("error:", err.getvalue())
