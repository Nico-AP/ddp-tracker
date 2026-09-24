import json
from datetime import UTC, datetime
from pathlib import Path as FilePath
from unittest import TestCase

from ddp_parser.errors import InvalidDocumentError
from ddp_parser.model import (
    ContainerNode,
    CsvInfo,
    DataNode,
    Document,
    FileNode,
    FolderNode,
    JsonType,
    MediaNode,
    MimeSource,
    MinMax,
    ParseWarning,
    Samples,
    Shape,
    Source,
    Stats,
    UnmatchedNode,
    UnmatchedReason,
    from_dict,
    from_json,
    to_dict,
    to_json,
)

WORKED_EXAMPLE = FilePath(__file__).parent / "fixtures" / "worked_example.json"


class WorkedExampleTests(TestCase):
    """The spec's worked example (docs/docs/ddp_parser/index.md §8) must round-trip exactly."""

    def setUp(self):
        self.text = WORKED_EXAMPLE.read_text(encoding="utf-8")
        self.data = json.loads(self.text)
        self.document = from_dict(self.data)

    def test_round_trip_is_lossless(self):
        self.assertEqual(to_dict(self.document), self.data)

    def test_json_output_matches_spec_including_key_order(self):
        # Re-dump with json to normalise whitespace; key order is preserved by json.loads.
        normalised = json.dumps(json.loads(to_json(self.document)), indent=2, ensure_ascii=False)
        self.assertEqual(normalised + "\n", self.text)

    def test_model_reflects_spec_semantics(self):
        root = self.document.root
        assert isinstance(root, ContainerNode)
        self.assertEqual(root.path, "")
        profile = root.children[1]
        assert isinstance(profile, FileNode)
        self.assertEqual(profile.type, JsonType.OBJECT)
        assert profile.properties is not None
        posts_item = profile.properties["posts"].items
        assert posts_item is not None
        assert posts_item.properties is not None
        location = posts_item.properties["location"]
        self.assertEqual(location.stats, Stats(count=3, present=1, null=0))
        self.assertEqual(location.path, "/profile.json/posts/[]/location")
        self.assertEqual(posts_item.properties["text"].type, (JsonType.NULL, JsonType.STRING))

    def test_from_json(self):
        self.assertEqual(from_json(self.text), self.document)


def _data(path, type_=JsonType.STRING, **kwargs):
    return DataNode(
        name=kwargs.pop("name", None),
        path=path,
        type=type_,
        stats=kwargs.pop("stats", Stats(1, 1)),
        **kwargs,
    )


class AllKindsRoundTripTests(TestCase):
    def setUp(self):
        modified = datetime(2026, 8, 1, 10, 12, 4)  # noqa: DTZ001 - zip times are naive by spec
        group = "/inbox/message_{n}.json"
        properties = {
            "sent": _data(
                f"{group}/sent",
                name="sent",
                shape=Shape.DATE,
                shapes={Shape.DATE: 4},
                formats={"%d/%m/%Y": 2, "%m/%d/%Y": 2},
                stats=Stats(4, 4),
            ),
            "at": _data(
                f"{group}/at",
                name="at",
                shape=Shape.DATETIME,
                format="%Y-%m-%dT%H:%M:%S.%3f",
                length=MinMax(23, 23),
            ),
            "n": _data(
                f"{group}/n",
                JsonType.INTEGER,
                name="n",
                shape=Shape.PLAIN,
                range=MinMax(-1, 2.5),
                samples=Samples((1, 2), redacted=False),
            ),
            "a/b": _data(
                f"{group}/a~1b",
                JsonType.ARRAY,
                name="a/b",
                items=_data(f"{group}/a~1b/[]", JsonType.NULL),
            ),
        }
        self.document = Document(
            parser_version="0.1.0",
            created_at=datetime(2026, 9, 24, 10, 0, tzinfo=UTC),
            source=Source("export.zip", 100, "ab" * 32),
            options={"samples": True, "shape_threshold": 0.95},
            warnings=(
                ParseWarning(code="ambiguous_date_order", path=f"{group}/sent"),
                ParseWarning(code="path_traversal", message="../evil"),
            ),
            root=ContainerNode(
                name="export.zip",
                path="",
                size_bytes=100,
                ext=".zip",
                children=(
                    FolderNode(
                        name="inbox",
                        path="/inbox",
                        children=(
                            FileNode(
                                name="message_{n}.json",
                                path=group,
                                size_bytes=10,
                                modified=modified,
                                ext=".json",
                                mime="application/json",
                                mime_source=MimeSource.EXTENSION,
                                parser="json",
                                encoding="utf-8",
                                files=40,
                                type=JsonType.OBJECT,
                                stats=Stats(40, 40),
                                properties=properties,
                            ),
                        ),
                    ),
                    FileNode(
                        name="posts.csv",
                        path="/posts.csv",
                        parser="csv",
                        csv=CsvInfo(delimiter=";", quotechar='"'),
                        type=JsonType.ARRAY,
                        stats=Stats(1, 1),
                    ),
                    FileNode(
                        name="tweets.js",
                        path="/tweets.js",
                        parser="js-json",
                        wrapper="window.YTD.tweets.part0 =",
                        type=JsonType.ARRAY,
                        stats=Stats(1, 1),
                    ),
                    MediaNode(name="a.jpg", path="/a.jpg", mime="image/jpeg"),
                    UnmatchedNode(
                        name="broken_{n}.json",
                        path="/broken_{n}.json",
                        reason=UnmatchedReason.PARSE_ERROR,
                        error="Expecting value: line 1",
                        files=2,
                    ),
                ),
            ),
        )

    def _group_file(self):
        return to_dict(self.document)["root"]["children"][0]["children"][0]

    def test_round_trip(self):
        self.assertEqual(from_dict(to_dict(self.document)), self.document)

    def test_json_round_trip(self):
        self.assertEqual(from_json(to_json(self.document)), self.document)

    def test_unresolved_format_is_omitted(self):
        sent = self._group_file()["properties"]["sent"]
        self.assertNotIn("format", sent)
        self.assertEqual(sent["formats"], {"%d/%m/%Y": 2, "%m/%d/%Y": 2})

    def test_file_carries_content_inline(self):
        group_file = self._group_file()
        self.assertNotIn("content", group_file)
        self.assertEqual(group_file["type"], "object")
        self.assertEqual(group_file["files"], 40)
        self.assertEqual(group_file["stats"], {"count": 40, "present": 40, "null": 0})
        self.assertEqual(group_file["path"], "/inbox/message_{n}.json")

    def test_file_key_order_puts_file_details_before_schema(self):
        keys = list(self._group_file())
        self.assertEqual(keys[:3], ["kind", "name", "path"])
        self.assertLess(keys.index("parser"), keys.index("type"))
        self.assertLess(keys.index("files"), keys.index("stats"))

    def test_none_metadata_is_omitted(self):
        folder = to_dict(self.document)["root"]["children"][0]
        self.assertNotIn("size_bytes", folder)
        self.assertNotIn("modified", folder)


class InvalidDocumentTests(TestCase):
    def setUp(self):
        self.data = json.loads(WORKED_EXAMPLE.read_text(encoding="utf-8"))

    def test_missing_root(self):
        del self.data["root"]
        with self.assertRaises(InvalidDocumentError):
            from_dict(self.data)

    def test_unknown_kind(self):
        self.data["root"]["kind"] = "archive"
        with self.assertRaises(InvalidDocumentError):
            from_dict(self.data)

    def test_data_node_as_root(self):
        self.data["root"] = self.data["root"]["children"][0]["items"]
        with self.assertRaises(InvalidDocumentError):
            from_dict(self.data)

    def test_fs_node_as_array_items(self):
        csv_file = self.data["root"]["children"][0]
        csv_file["items"] = dict(csv_file)
        with self.assertRaises(InvalidDocumentError):
            from_dict(self.data)

    def test_invalid_json(self):
        with self.assertRaises(InvalidDocumentError):
            from_json("{not json")

    def test_invalid_path(self):
        self.data["root"]["children"][0]["path"] = "no-leading-slash"
        with self.assertRaises(InvalidDocumentError):
            from_dict(self.data)
