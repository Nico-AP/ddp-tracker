import hashlib
import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import TestCase

from ddp_parser.errors import LimitExceededError
from ddp_parser.model import MimeSource, ParseWarning
from ddp_parser.options import Options
from ddp_parser.source import Entry, ReadBudget, open_input, plan, read_zip
from ddp_parser.source.grouping import group_names, mask_name
from ddp_parser.source.mime import detect_mime, is_media, is_zip
from ddp_parser.source.unwrap import same_name, unwrap
from ddp_parser.source.zip import decode_name, is_junk

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def make_zip(members: dict[str, bytes], *, date_time=(2026, 9, 20, 14, 2, 10)) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=date_time), data)
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))


def entry(*parts: str, data: bytes = b"", is_dir: bool = False) -> Entry:
    return Entry(
        parts=parts, size=len(data), modified=None, is_dir=is_dir, open=lambda: io.BytesIO(data)
    )


def read(members: dict[str, bytes], options: Options | None = None, **kwargs):
    warnings: list[ParseWarning] = []
    entries = read_zip(make_zip(members, **kwargs), options or Options(), warnings)
    return entries, warnings


class DecodeNameTests(TestCase):
    def test_utf8_written_without_flag_is_repaired(self):
        info = zipfile.ZipInfo("Kanäle.json".encode().decode("cp437"))
        self.assertEqual(decode_name(info), "Kanäle.json")

    def test_real_cp437_name_is_kept(self):
        info = zipfile.ZipInfo(b"Caf\x82.json".decode("cp437"))
        self.assertEqual(decode_name(info), "Café.json")

    def test_flagged_name_is_not_touched(self):
        info = zipfile.ZipInfo("├ñ.json")
        info.flag_bits |= 0x800
        self.assertEqual(decode_name(info), "├ñ.json")

    def test_names_are_nfc(self):
        self.assertEqual(decode_name(zipfile.ZipInfo("Kana\u0308le")), "Kan\u00e4le")


class ReadZipTests(TestCase):
    def test_entries(self):
        entries, warnings = read({"inbox/": b"", "inbox/a.json": b"{}", "b.csv": b"x"})
        self.assertEqual([e.parts for e in entries], [("inbox",), ("inbox", "a.json"), ("b.csv",)])
        self.assertTrue(entries[0].is_dir)
        self.assertEqual(entries[1].size, 2)
        self.assertEqual(entries[1].modified, datetime(2026, 9, 20, 14, 2, 10))  # noqa: DTZ001
        with entries[1].open() as stream:
            self.assertEqual(stream.read(), b"{}")
        self.assertEqual(warnings, [])

    def test_unsafe_paths_are_rejected(self):
        entries, warnings = read(
            {"../evil.json": b"", "/abs.json": b"", "C:/x.json": b"", "ok": b""}
        )
        self.assertEqual([e.parts for e in entries], [("ok",)])
        self.assertEqual([w.code for w in warnings], ["unsafe_path"] * 3)

    def test_backslash_separators(self):
        entries, _ = read({"inbox\\a.json": b""})
        self.assertEqual(entries[0].parts, ("inbox", "a.json"))

    def test_junk_is_dropped_with_one_warning(self):
        members = {
            "__MACOSX/._a.json": b"",
            "._b.json": b"",
            ".DS_Store": b"",
            "Thumbs.db": b"",
            "a.json": b"",
        }
        entries, warnings = read(members)
        self.assertEqual([e.parts for e in entries], [("a.json",)])
        self.assertEqual(
            [(w.code, w.message) for w in warnings],
            [("ignored_entries", "4 OS junk entries dropped")],
        )

    def test_junk_can_be_kept(self):
        entries, warnings = read({".DS_Store": b"", "a.json": b""}, Options(keep_ignored=True))
        self.assertEqual([e.ignored for e in entries], [True, False])
        self.assertEqual(warnings, [])

    def test_duplicates_keep_the_last(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("a.json", b"1")
            with self.assertWarns(UserWarning):  # zipfile itself warns about the duplicate
                archive.writestr("a.json", b"22")
        warnings: list[ParseWarning] = []
        entries = read_zip(zipfile.ZipFile(buffer), Options(), warnings)
        self.assertEqual([e.size for e in entries], [2])
        self.assertEqual([w.code for w in warnings], ["duplicate_entry"])

    def test_entry_limit(self):
        entries, warnings = read({f"{i}.json": b"" for i in range(5)}, Options(max_entries=3))
        self.assertEqual(len(entries), 3)
        self.assertEqual(
            [(w.code, w.message) for w in warnings], [("too_many_entries", "2 entries skipped")]
        )

    def test_separator_only_names_are_skipped(self):
        entries, _ = read({"/": b"", "a": b""})
        self.assertEqual([e.parts for e in entries], [("a",)])

    def test_header_reads_only_the_start(self):
        self.assertEqual(entry("a", data=PNG).header(8), PNG[:8])

    def test_unset_timestamp(self):
        entries, _ = read({"a": b""}, date_time=(1980, 0, 0, 0, 0, 0))
        self.assertIsNone(entries[0].modified)

    def test_is_junk(self):
        self.assertTrue(is_junk(("a", "__MACOSX", "b")))
        self.assertTrue(is_junk(("desktop.INI",)))
        self.assertFalse(is_junk(("a", "b.json")))


class ReadBudgetTests(TestCase):
    def test_reads_within_limits(self):
        budget = ReadBudget(Options(max_entry_size=4, max_total_size=6))
        self.assertEqual(budget.read(entry("a", data=b"1234")), b"1234")
        with self.assertRaises(LimitExceededError):  # per entry
            budget.read(entry("b", data=b"12345"))
        with self.assertRaises(LimitExceededError):  # total: 4 of 6 used
            budget.read(entry("c", data=b"123"))
        self.assertEqual(budget.read(entry("d", data=b"12")), b"12")

    def test_entry_larger_than_declared(self):
        lying = Entry(parts=("a",), size=2, modified=None, open=lambda: io.BytesIO(b"12345"))
        with self.assertRaises(LimitExceededError):
            ReadBudget(Options()).read(lying)


class GroupingTests(TestCase):
    def test_groups_need_two_members(self):
        names = [
            "message_1.json",
            "message_2.json",
            "photo_1.jpg",
            "profile.json",
            "archive_1.zip",
            "archive_2.zip",
        ]
        self.assertEqual(
            group_names(names),
            {"message_1.json": "message_{n}.json", "message_2.json": "message_{n}.json"},
        )

    def test_every_digit_run_is_a_placeholder(self):
        names = [
            "2023_12_posts.json",
            "2024_01_posts.json",
            "IMG_20240101_120000.jpg",
            "IMG_20240102_093000.jpg",
        ]
        self.assertEqual(
            set(group_names(names).values()), {"{n}_{n}_posts.json", "IMG_{n}_{n}.jpg"}
        )


class PlanTests(TestCase):
    def test_tree_with_implicit_folders_and_groups(self):
        modified = datetime(2026, 1, 1)  # noqa: DTZ001
        entries = [
            Entry(parts=("messages",), size=0, modified=modified, is_dir=True, open=io.BytesIO),
            entry("messages", "inbox", "chat_1", "message_1.json"),
            entry("messages", "inbox", "chat_1", "message_2.json"),
            entry("messages", "inbox", "chat_1", "photo.jpg"),
            entry("profile.json"),
        ]
        root = plan(entries, Options(), name="export.zip")
        self.assertEqual((root.name, root.path), ("export.zip", ""))
        self.assertEqual([f.name for f in root.files], ["profile.json"])
        messages = root.folders["messages"]
        self.assertEqual(messages.modified, modified)
        chat = messages.folders["inbox"].folders["chat_1"]
        self.assertEqual(chat.path, "/messages/inbox/chat_1")
        self.assertEqual(
            [(f.name, f.path, len(f.entries), f.is_group) for f in chat.files],
            [
                ("message_{n}.json", "/messages/inbox/chat_1/message_{n}.json", 2, True),
                ("photo.jpg", "/messages/inbox/chat_1/photo.jpg", 1, False),
            ],
        )

    def test_nested_container_path(self):
        root = plan([entry("a.json")], Options(), name="inner.zip", path="/outer/inner.zip")
        self.assertEqual(root.files[0].path, "/outer/inner.zip/a.json")

    def test_names_are_escaped_in_paths(self):
        root = plan([entry("a~b", "c.json")], Options())
        self.assertEqual(root.folders["a~b"].files[0].path, "/a~0b/c.json")


class MimeTests(TestCase):
    def test_magic_before_extension(self):
        self.assertEqual(detect_mime("photo.dat", PNG), ("image/png", MimeSource.MAGIC))
        self.assertEqual(
            detect_mime("posts.json", b"{}"), ("application/json", MimeSource.EXTENSION)
        )
        self.assertEqual(detect_mime("README", b"hello"), (None, None))

    def test_media_and_zip(self):
        self.assertTrue(is_media("video/mp4"))
        self.assertFalse(is_media("application/json"))
        self.assertFalse(is_media(None))
        self.assertTrue(is_zip("Inner.ZIP"))
        self.assertFalse(is_zip("report.docx"))


class OpenInputTests(TestCase):
    def test_bytes_path_and_stream(self):
        data = b"hello"
        digest = hashlib.sha256(data).hexdigest()
        from_bytes = open_input(data, name="x.txt")
        self.assertEqual(
            (from_bytes.name, from_bytes.size, from_bytes.sha256), ("x.txt", 5, digest)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.zip"
            path.write_bytes(data)
            from_path = open_input(path)
            with from_path.stream:
                self.assertEqual((from_path.name, from_path.sha256), ("export.zip", digest))
                self.assertEqual(from_path.stream.read(), data)  # rewound after hashing
            with path.open("rb") as stream:
                self.assertEqual(open_input(stream).name, "export.zip")
        self.assertIsNone(open_input(io.BytesIO(data)).name)

    def test_is_zip(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("a", b"")
        self.assertTrue(open_input(buffer.getvalue()).is_zip)
        self.assertFalse(open_input(b"{}").is_zip)


def inbox(*threads: tuple[str, list[str]]) -> list[Entry]:
    return [
        entry("messages", "inbox", thread, *name.split("/"))
        for thread, names in threads
        for name in names
    ]


class CollapseTests(TestCase):
    def test_mask_name(self):
        cases = {
            "johndoe_1234": "xs0",
            "annasmith_98765": "xs0",
            "2024-01": "0s0",
            "Zürich": "x",
            "a b.c": "xsxsx",
        }
        for name, mask in cases.items():
            with self.subTest(name=name):
                self.assertEqual(mask_name(name), mask)

    def test_look_alike_threads_collapse(self):
        entries = inbox(
            ("johndoe_1234", ["message_1.json", "photos/a.jpg"]),
            ("janedoe_5678", ["message_1.json", "message_2.json"]),
            ("chat-group_42", ["message_1.json"]),
        )
        messages = plan(entries, Options()).folders["messages"].folders["inbox"]
        self.assertEqual(list(messages.folders), ["{*}"])
        thread = messages.folders["{*}"]
        self.assertEqual(
            (thread.name, thread.path, thread.collapsed), ("xs0", "/messages/inbox/{*}", 3)
        )
        self.assertEqual(
            [(f.name, f.path, len(f.entries)) for f in thread.files],
            [("message_{n}.json", "/messages/inbox/{*}/message_{n}.json", 4)],
        )
        self.assertEqual(thread.folders["photos"].files[0].path, "/messages/inbox/{*}/photos/a.jpg")

    def test_different_folders_stay(self):
        entries = [
            entry("ads", "advertisers.json"),
            entry("posts", "your_posts_1.json"),
            entry("profile", "profile.json"),
        ]
        self.assertEqual(list(plan(entries, Options()).folders), ["ads", "posts", "profile"])

    def test_two_folders_need_real_overlap(self):
        entries = [
            entry("a", "x.json"),
            entry("a", "y.json"),
            entry("b", "x.json"),
            entry("b", "z.json"),
            entry("b", "w.json"),
        ]
        self.assertEqual(
            list(plan(entries, Options()).folders), ["a", "b"]
        )  # 1 of 2 / 1 of 3 shared
        entries = [
            entry("a", "x.json"),
            entry("a", "y.json"),
            entry("b", "x.json"),
            entry("b", "y.json"),
        ]
        self.assertEqual(list(plan(entries, Options()).folders), ["{*}"])

    def test_folders_with_loose_files_or_single_child_stay(self):
        entries = [entry("readme.json"), entry("a_1", "m.json"), entry("a_2", "m.json")]
        self.assertEqual(list(plan(entries, Options()).folders), ["a_1", "a_2"])
        self.assertEqual(list(plan([entry("only", "m.json")], Options()).folders), ["only"])

    def test_empty_subfolders_do_not_collapse(self):
        entries = [
            Entry(parts=(n,), size=0, modified=None, is_dir=True, open=io.BytesIO)
            for n in ("x", "y")
        ]
        self.assertEqual(list(plan(entries, Options()).folders), ["x", "y"])

    def test_rules_override_the_heuristic(self):
        different = [entry("root", "ads", "a.json"), entry("root", "posts", "b.json")]
        forced = plan(different, Options(collapse_folders=("/*",)))
        self.assertEqual(list(forced.folders["root"].folders), ["{*}"])
        alike = [entry("t", "a_1", "m.json"), entry("t", "a_2", "m.json")]
        kept = plan(alike, Options(keep_folders=("/t",)))
        self.assertEqual(list(kept.folders["t"].folders), ["a_1", "a_2"])

    def test_rule_masks_even_a_single_folder(self):
        stamp = datetime(2026, 1, 1)  # noqa: DTZ001
        entries = [
            Entry(
                parts=("inbox", "johndoe_1234"),
                size=0,
                modified=stamp,
                is_dir=True,
                open=io.BytesIO,
            ),
            entry("inbox", "johndoe_1234", "m.json"),
        ]
        only = plan(entries, Options(collapse_folders=("/inbox",))).folders["inbox"].folders["{*}"]
        self.assertEqual((only.name, only.collapsed, only.modified), ("xs0", 1, stamp))

    def test_merged_folder_keeps_modified_only_when_single(self):
        stamp = datetime(2026, 1, 1)  # noqa: DTZ001
        entries = [
            Entry(parts=("a_1", "sub"), size=0, modified=stamp, is_dir=True, open=io.BytesIO),
            entry("a_1", "sub", "m.json"),
            entry("a_2", "m.json"),
            entry("a_1", "m.json"),
        ]
        collapsed = plan(entries, Options()).folders["{*}"]
        self.assertIsNone(collapsed.modified)
        self.assertEqual(collapsed.folders["sub"].modified, stamp)


def junk(*parts: str) -> Entry:
    return Entry(parts=parts, size=0, modified=None, ignored=True, open=io.BytesIO)


class UnwrapTests(TestCase):
    ZIP = "instagram-johndoe-2026-09-29-AbCd1234.zip"
    TOP = "instagram-johndoe-2026-09-29-AbCd1234"

    def test_folder_named_like_the_zip_is_dropped(self):
        entries = [entry(self.TOP, is_dir=True), entry(self.TOP, "ads", "a.json")]
        unwrapped, dropped = unwrap(entries, self.ZIP)
        self.assertTrue(dropped)
        self.assertEqual([e.parts for e in unwrapped], [("ads", "a.json")])

    def test_names_match_ignoring_case_and_copy_suffixes(self):
        for folder, container in [
            (self.TOP, "Instagram-JohnDoe-2026-09-29-AbCd1234 (1).zip"),
            (self.TOP + " 2", self.ZIP),
            (self.TOP + " - Copy", self.ZIP),
            ("Kana\u0308le", "Kan\u00e4le.zip"),
        ]:
            with self.subTest(folder=folder, container=container):
                self.assertTrue(same_name(folder, container))
        self.assertFalse(same_name("Takeout", self.ZIP))

    def test_other_names_are_kept(self):
        entries = [entry("Takeout", "a.json")]
        self.assertEqual(unwrap(entries, "takeout-20260929.zip"), (entries, False))

    def test_several_top_level_entries_are_kept(self):
        entries = [entry(self.TOP, "a.json"), entry("b.json")]
        self.assertEqual(unwrap(entries, self.ZIP), (entries, False))

    def test_folder_without_files_is_kept(self):
        entries = [entry(self.TOP, is_dir=True), entry(self.TOP, "ads", is_dir=True)]
        self.assertEqual(unwrap(entries, self.ZIP), (entries, False))

    def test_unnamed_container_is_kept(self):
        entries = [entry(self.TOP, "a.json")]
        self.assertEqual(unwrap(entries, None), (entries, False))

    def test_os_junk_is_not_counted_and_only_moved_inside(self):
        entries = [
            entry(self.TOP, "a.json"),
            junk("__MACOSX", self.TOP, "._a.json"),
            junk(self.TOP, ".DS_Store"),
        ]
        unwrapped, dropped = unwrap(entries, self.ZIP)
        self.assertTrue(dropped)
        self.assertEqual(
            [e.parts for e in unwrapped],
            [("a.json",), ("__MACOSX", self.TOP, "._a.json"), (".DS_Store",)],
        )
