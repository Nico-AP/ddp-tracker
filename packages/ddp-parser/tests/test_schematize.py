import json
from pathlib import Path
from unittest import TestCase

import msgspec

from ddp_parser.model import FileNode, JsonType, MinMax, ParseWarning, Samples, Shape, Stats
from ddp_parser.options import Options
from ddp_parser.schematize import NodeBuilder, data_fields
from ddp_parser.schematize.samples import mask

WORKED_EXAMPLE = Path(__file__).parent / "fixtures" / "worked_example.json"
DATA_KEYS = {"type", "shape", "format", "formats", "length", "range", "stats", "shapes"}
DATA_KEYS |= {"properties", "items", "samples"}

PROFILE = {
    "user": {"name": "Anna Muster", "email": "anna@example.com", "joined": "2021-03-14T09:26:53Z"},
    "settings": {"language": "de", "notifications": True},
    "posts": [
        {"id": 101, "text": "Hello world", "likes": 3},
        {"id": 102, "text": "Zurich in autumn", "likes": 12, "location": "Zurich"},
        {"id": 103, "text": None, "likes": 0},
    ],
}
# CSV rows after the parser's type inference.
LOGINS = [
    {"timestamp": 1767225600, "action": "login", "device": "iPhone"},
    {"timestamp": 1767312000, "action": "logout", "device": ""},
    {"timestamp": 1767398400, "action": "login", "device": "MacBook"},
]


def schematize(value, *, name="file.json", options=None, observe_as_array=False):
    builder = NodeBuilder(name, "/" + name, max_samples=(options or Options()).max_samples)
    if observe_as_array:
        builder.observe_array(value)
    else:
        builder.observe(value)
    warnings: list[ParseWarning] = []
    node = builder.build(options or Options(), warnings)
    return node, warnings


class WorkedExampleTests(TestCase):
    """Schematizing the raw values of spec §8 yields exactly the spec's data fields."""

    def setUp(self):
        fixture = json.loads(WORKED_EXAMPLE.read_text(encoding="utf-8"))
        self.expected = {child["name"]: child for child in fixture["root"]["children"]}

    def check(self, name, value, **kwargs):
        node, warnings = schematize(value, name=name, **kwargs)
        got = msgspec.to_builtins(msgspec.json.decode(msgspec.json.encode(node)))
        want = {k: v for k, v in self.expected[name].items() if k in DATA_KEYS}
        self.assertEqual({k: v for k, v in got.items() if k in DATA_KEYS}, want)
        self.assertEqual(warnings, [])

    def test_profile_json(self):
        self.check("profile.json", PROFILE)

    def test_logins_csv_streamed_rows(self):
        self.check("logins.csv", iter(LOGINS), observe_as_array=True)


class StatsTests(TestCase):
    def test_optional_key_and_null(self):
        node, _ = schematize([{"a": 1, "b": None}, {"a": 2}, {"a": 3, "b": "x"}])
        assert node.items is not None
        assert node.items.properties is not None
        b = node.items.properties["b"]
        self.assertEqual(b.stats, Stats(count=3, present=2, null=1))
        self.assertEqual(b.type, (JsonType.NULL, JsonType.STRING))

    def test_key_first_seen_late_gets_full_count(self):
        node, _ = schematize([{}, {}, {"late": True}])
        assert node.items is not None
        assert node.items.properties is not None
        self.assertEqual(node.items.properties["late"].stats, Stats(count=3, present=1))

    def test_merging_files_is_observing_twice(self):
        builder = NodeBuilder("message_{n}.json", "/message_{n}.json")
        builder.observe({"messages": [{"text": "hi"}]})
        builder.observe({"messages": [{"text": "yo"}, {"text": "hey", "photo": "a.jpg"}]})
        node = builder.build(Options(), [])
        self.assertEqual(node.stats, Stats(2, 2))
        assert node.properties is not None
        messages = node.properties["messages"]
        self.assertEqual(messages.length, MinMax(1, 2))
        assert messages.items is not None
        assert messages.items.properties is not None
        self.assertEqual(messages.items.properties["photo"].stats, Stats(3, 1))

    def test_empty_array_has_no_items(self):
        node, _ = schematize([])
        self.assertIsNone(node.items)
        self.assertEqual(node.length, MinMax(0, 0))


class TypeAndShapeTests(TestCase):
    def test_integer_and_number_unify_to_number(self):
        node, _ = schematize([1, 2.5])
        assert node.items is not None
        self.assertEqual(node.items.type, JsonType.NUMBER)

    def test_booleans_and_objects_have_no_shape(self):
        node, _ = schematize({"flag": True})
        assert node.properties is not None
        self.assertIsNone(node.shape)
        self.assertIsNone(node.properties["flag"].shape)
        self.assertEqual(node.properties["flag"].shapes, {})

    def test_threshold_and_mixed(self):
        values = ["abc"] * 19 + ["a b"]  # 95 % alpha
        node, _ = schematize(values)
        assert node.items is not None
        self.assertEqual(node.items.shape, Shape.ALPHA)
        node, _ = schematize(values, options=Options(shape_threshold=0.99))
        assert node.items is not None
        self.assertEqual(node.items.shape, Shape.MIXED)

    def test_only_empty_strings(self):
        node, _ = schematize(["", " "])
        assert node.items is not None
        self.assertEqual(node.items.shape, Shape.EMPTY)

    def test_id_key_is_plain(self):
        node, _ = schematize({"user_id": 1767225600, "created": 1767225600})
        assert node.properties is not None
        self.assertEqual(node.properties["user_id"].shape, Shape.PLAIN)
        self.assertEqual(node.properties["created"].format, "s")

    def test_non_json_value_is_rejected(self):
        with self.assertRaises(TypeError):
            schematize({"when": object()})


class FormatTests(TestCase):
    def test_all_values_decide_date_order(self):
        node, warnings = schematize(["01/02/2026", "13/02/2026"])
        assert node.items is not None
        self.assertEqual(node.items.format, "%d/%m/%Y")
        self.assertEqual(warnings, [])

    def test_ambiguous_date_order_warns(self):
        node, warnings = schematize(["01/02/2026", "03/04/2026"])
        assert node.items is not None
        self.assertIsNone(node.items.format)
        self.assertEqual(node.items.formats, {"%d/%m/%Y": 2, "%m/%d/%Y": 2})
        self.assertEqual([w.code for w in warnings], ["ambiguous_date_order"])
        self.assertEqual(warnings[0].path, "/file.json/[]")

    def test_different_formats_are_counted(self):
        node, _ = schematize(["2024-01-01", "2024-01-02", "01.02.2024"])
        assert node.items is not None
        self.assertIsNone(node.items.format)
        self.assertEqual(node.items.formats, {"%Y-%m-%d": 2, "%d.%m.%Y": 1})

    def test_mixed_unix_units(self):
        node, _ = schematize([1767225600, 1767225600000])
        assert node.items is not None
        self.assertEqual(node.items.formats, {"ms": 1, "s": 1})


class WarningTests(TestCase):
    def test_reserved_key(self):
        _, warnings = schematize({"[]": 1})
        self.assertEqual([(w.code, w.path) for w in warnings], [("reserved_name", "/file.json/[]")])


class SamplesTests(TestCase):
    def test_off_by_default_including_range(self):
        node, _ = schematize({"n": 5, "s": "x"})
        assert node.properties is not None
        self.assertIsNone(node.properties["n"].samples)
        self.assertIsNone(node.properties["n"].range)

    def test_samples_range_and_masking(self):
        options = Options(samples=True, max_samples=2)
        node, _ = schematize(
            {"n": [5, 1, 9], "email": ["anna@example.com"], "lang": ["de"]}, options=options
        )
        assert node.properties is not None
        n = node.properties["n"].items
        assert n is not None
        self.assertEqual(n.range, MinMax(1, 9))
        self.assertEqual(n.samples, Samples((5, 1), redacted=False))
        email, lang = node.properties["email"].items, node.properties["lang"].items
        assert email is not None
        assert lang is not None
        self.assertEqual(email.samples, Samples(("axxx@xxxxxxx.xxx",), redacted=True))
        self.assertEqual(lang.samples, Samples(("de",), redacted=False))

    def test_distinct_values_only(self):
        node, _ = schematize([1, 1, True, "1"], options=Options(samples=True))
        assert node.items is not None
        assert node.items.samples is not None
        self.assertEqual(node.items.samples.values, (1, True, "1"))

    def test_masked_shapes_are_an_option(self):
        options = Options(samples=True, masked_shapes=("email",))
        node, _ = schematize({"email": "anna@example.com", "note": "Hi there"}, options=options)
        assert node.properties is not None
        self.assertEqual(
            node.properties["email"].samples, Samples(("axxx@xxxxxxx.xxx",), redacted=True)
        )
        self.assertEqual(node.properties["note"].samples, Samples(("Hi there",), redacted=False))

    def test_mask(self):
        self.assertEqual(mask("https://ex.com/a1"), "hxxxx://xx.xxx/x0")
        self.assertEqual(mask(""), "")


class DataFieldsTests(TestCase):
    def test_file_node_from_data_node(self):
        node, _ = schematize({"a": 1}, name="a.json")
        file_node = FileNode(name="a.json", path="/a.json", parser="json", **data_fields(node))
        self.assertEqual(file_node.properties, node.properties)
        self.assertEqual(file_node.stats, node.stats)


class OptionsTests(TestCase):
    def test_to_dict_is_recorded_in_documents(self):
        recorded = Options(samples=True, keep_folders=("/a",)).to_dict()
        self.assertEqual(recorded["samples"], True)
        self.assertEqual(recorded["keep_folders"], ["/a"])  # JSON-ready
        self.assertEqual(
            set(recorded),
            {
                "samples",
                "max_samples",
                "masked_shapes",
                "shape_threshold",
                "max_depth",
                "max_entries",
                "max_entry_size",
                "max_total_size",
                "keep_ignored",
                "collapse_folders",
                "keep_folders",
            },
        )
