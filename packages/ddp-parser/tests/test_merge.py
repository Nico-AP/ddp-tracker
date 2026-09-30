import io
import zipfile
from unittest import TestCase

from ddp_parser import Options, merge, merge_trees, parse
from ddp_parser.model import FileNode, FolderNode, JsonType, MinMax, Stats


def doc(members: dict[str, bytes]):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return parse(buffer.getvalue(), name="export.zip")


def names(node):
    return [c.name for c in node.children]


def child(node, name):
    return next(c for c in node.children if c.name == name)


class MergeTests(TestCase):
    def test_needs_a_document(self):
        with self.assertRaises(ValueError):
            merge([])

    def test_single_document_is_unchanged(self):
        document = doc({"a.json": b'{"x": 1}'})
        merged = merge([document])
        self.assertEqual(merged.root, document.root)
        self.assertEqual((merged.documents, merged.presence["/a.json/x"]), (1, 1))

    def test_presence_counts_documents(self):
        merged = merge([doc({"a.json": b"{}", "b.json": b"{}"}), doc({"a.json": b"{}"})])
        self.assertEqual(merged.presence, {"": 2, "/a.json": 2, "/b.json": 1})
        self.assertEqual(names(merged.root), ["a.json", "b.json"])

    def test_stats_and_optional_keys(self):
        merged = merge([doc({"a.json": b'{"x": 1, "y": 2}'}), doc({"a.json": b'{"x": 3}'})])
        file = child(merged.root, "a.json")
        assert isinstance(file, FileNode)
        assert file.properties is not None
        self.assertEqual(file.stats, Stats(2, 2))
        self.assertEqual(file.properties["x"].stats, Stats(2, 2))
        self.assertEqual(file.properties["y"].stats, Stats(2, 1))  # optional across exports

    def test_key_under_a_non_object_on_the_other_side(self):
        merged = merge([doc({"a.json": b'{"x": {"k": 1}}'}), doc({"a.json": b'{"x": "text"}'})])
        x = child(merged.root, "a.json").properties["x"]
        self.assertEqual(x.type, (JsonType.OBJECT, JsonType.STRING))
        self.assertEqual(x.properties["k"].stats, Stats(1, 1))

    def test_type_unions(self):
        merged = merge(
            [doc({"a.json": b'{"x": 1, "n": 1}'}), doc({"a.json": b'{"x": "s", "n": 2.5}'})]
        )
        props = child(merged.root, "a.json").properties
        self.assertEqual(props["x"].type, (JsonType.INTEGER, JsonType.STRING))
        self.assertEqual(props["n"].type, JsonType.NUMBER)

    def test_lengths_and_items(self):
        merged = merge(
            [doc({"a.json": b'{"l": ["ab"]}'}), doc({"a.json": b'{"l": ["abcd", "c"], "e": []}'})]
        )
        props = child(merged.root, "a.json").properties
        self.assertEqual(props["l"].length, MinMax(1, 2))
        self.assertEqual(props["l"].items.length, MinMax(1, 4))
        self.assertEqual(props["l"].items.stats, Stats(3, 3))

    def test_formats(self):
        same = merge([doc({"a.json": b'["2024-01-01"]'}), doc({"a.json": b'["2024-02-02"]'})])
        self.assertEqual(child(same.root, "a.json").items.format, "%Y-%m-%d")
        different = merge(
            [doc({"a.json": b'["2024-01-01"]'}), doc({"a.json": b'["01.02.2024", "03.02.2024"]'})]
        )
        items = child(different.root, "a.json").items
        self.assertIsNone(items.format)
        self.assertEqual(items.formats, {"%Y-%m-%d": 1, "%d.%m.%Y": 2})

    def test_parsed_file_beats_failed_one(self):
        merged = merge([doc({"a.json": b"{"}), doc({"a.json": b'{"x": 1}'})])
        self.assertIsInstance(child(merged.root, "a.json"), FileNode)

    def test_groups_and_collapsed_folders_add_up(self):
        first = doc(
            {"m_1.json": b"{}", "m_2.json": b"{}", "t/a_1/x.json": b"{}", "t/a_2/x.json": b"{}"}
        )
        second = doc(
            {
                "m_1.json": b"{}",
                "m_2.json": b"{}",
                "m_3.json": b"{}",
                "t/b_1/x.json": b"{}",
                "t/b_2/x.json": b"{}",
            }
        )
        merged = merge([first, second])
        self.assertEqual(child(merged.root, "m_{n}.json").files, 5)
        collapsed = child(child(merged.root, "t"), "xs0")
        assert isinstance(collapsed, FolderNode)
        self.assertEqual(collapsed.folders, 4)

    def test_samples_and_ranges(self):
        options = Options(samples=True)
        first = parse(b"[1, 5]", options, name="a.json")
        second = parse(b"[9]", options, name="a.json")
        merged_root = merge([first, second]).root
        assert isinstance(merged_root, FileNode)
        items = merged_root.items
        assert items is not None
        assert items.samples is not None
        self.assertEqual(items.range, MinMax(1, 9))
        self.assertEqual(items.samples.values, (1, 5))  # at most as many as the larger side

    def test_media_and_unmatched(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
        members = {"p.jpg": png, "notes.pdf": b"%PDF-1.4"}
        merged = merge([doc(members), doc(members)])
        self.assertEqual(child(merged.root, "x.jpg").size_bytes, 2 * len(png))
        self.assertEqual(child(merged.root, "notes.pdf").reason, "unsupported_type")

    def test_format_counts_accumulate(self):
        documents = [
            doc({"a.json": b'["2024-01-01"]'}),
            doc({"a.json": b'["01.02.2024"]'}),
            doc({"a.json": b'["2024-03-03", "2024-04-04"]'}),
        ]
        items = child(merge(documents).root, "a.json").items
        self.assertEqual(items.formats, {"%Y-%m-%d": 3, "%d.%m.%Y": 1})

    def test_merge_trees(self):
        with self.assertRaises(ValueError):
            merge_trees([])
        first, second = doc({"a.json": b"{}"}), doc({"b.json": b"{}"})
        self.assertEqual(names(merge_trees([first.root, second.root])), ["a.json", "b.json"])
