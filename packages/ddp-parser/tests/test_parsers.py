import json
from pathlib import Path
from unittest import TestCase

import msgspec

from ddp_parser.errors import ParseError
from ddp_parser.model import CsvInfo, FileNode
from ddp_parser.options import Options
from ddp_parser.parsers import Parsed, parser_for
from ddp_parser.parsers.csv import clean_header, infer, parse_csv
from ddp_parser.parsers.encoding import decode
from ddp_parser.parsers.json import parse_js_json, parse_json, parse_json_lines
from ddp_parser.schematize import NodeBuilder, data_fields

WORKED_EXAMPLE = Path(__file__).parent / "fixtures" / "worked_example.json"

# The two files of the spec's worked example (index.md §8), byte for byte.
LOGINS_CSV = b"""timestamp,action,device
1767225600,login,iPhone
1767312000,logout,
1767398400,login,MacBook
"""
PROFILE_JSON = b"""{
  "user": {
    "name": "Anna Muster",
    "email": "anna@example.com",
    "joined": "2021-03-14T09:26:53Z"
  },
  "settings": {
    "language": "de",
    "notifications": true
  },
  "posts": [
    {"id": 101, "text": "Hello world", "likes": 3},
    {"id": 102, "text": "Zurich in autumn", "likes": 12, "location": "Zurich"},
    {"id": 103, "text": null, "likes": 0}
  ]
}
"""


def rows(parsed: Parsed) -> list[object]:
    assert parsed.items is not None
    return list(parsed.items)


class WorkedExampleTests(TestCase):
    """Parsing + schematizing the spec's example files yields the spec's file nodes."""

    def setUp(self):
        fixture = json.loads(WORKED_EXAMPLE.read_text(encoding="utf-8"))
        self.expected = {child["name"]: child for child in fixture["root"]["children"]}

    def check(self, name: str, data: bytes) -> None:
        parser = parser_for(name)
        assert parser is not None
        parsed = parser(data)
        builder = NodeBuilder(name, "/" + name)
        if parsed.items is not None:
            builder.observe_array(parsed.items)
        else:
            builder.observe(parsed.value)
        node = FileNode(
            name=name,
            path="/" + name,
            encoding=parsed.encoding,
            parser=parsed.parser,
            csv=parsed.csv,
            **data_fields(builder.build(Options(), [])),
        )
        got = msgspec.json.decode(msgspec.json.encode(node))
        want = self.expected[name]
        self.assertEqual(got, {key: value for key, value in want.items() if key in got})
        metadata = {"size_bytes", "modified", "ext", "mime", "mime_source"}
        self.assertEqual(set(want) - set(got), metadata)  # the rest comes from the zip source

    def test_logins_csv(self):
        self.check("logins.csv", LOGINS_CSV)

    def test_profile_json(self):
        self.check("profile.json", PROFILE_JSON)


class ParserForTests(TestCase):
    def test_extensions(self):
        cases = {
            "a.json": parse_json,
            "A.JSON": parse_json,
            "x/y.jsonl": parse_json_lines,
            "b.ndjson": parse_json_lines,
            "tweets.js": parse_js_json,
            "c.csv": parse_csv,
        }
        for name, parser in cases.items():
            with self.subTest(name=name):
                self.assertIs(parser_for(name), parser)

    def test_tsv_is_tab_separated_csv(self):
        parser = parser_for("d.tsv")
        assert parser is not None
        self.assertEqual(parser(b"a,b\tc\n1\t2\n").csv, CsvInfo(delimiter="\t", quotechar='"'))

    def test_unsupported(self):
        for name in ["photo.jpg", "notes.txt", "page.html", "README", ".json.bak"]:
            with self.subTest(name=name):
                self.assertIsNone(parser_for(name))


class EncodingTests(TestCase):
    def test_boms_and_utf8(self):
        text = "Zürich ✓"
        cases = [
            (text.encode("utf-8"), "utf-8"),
            (text.encode("utf-8-sig"), "utf-8-sig"),
            (b"\xff\xfe" + text.encode("utf-16-le"), "utf-16-le"),
            (b"\xfe\xff" + text.encode("utf-16-be"), "utf-16-be"),
            (b"\xff\xfe\x00\x00" + text.encode("utf-32-le"), "utf-32-le"),
        ]
        for data, encoding in cases:
            with self.subTest(encoding=encoding):
                self.assertEqual(decode(data), (text, encoding))

    def test_non_utf8_falls_back_to_cp1252(self):
        text = "Grüezi, café à Zürich \u2013 \u201cdéjà vu\u201d \u20ac"  # cp1252-only characters
        self.assertEqual(decode(text.encode("cp1252")), (text, "cp1252"))

    def test_undefined_cp1252_bytes_are_replaced(self):
        self.assertEqual(decode(b"a\x81b\xff"), ("a\ufffdbÿ", "cp1252"))


class JsonTests(TestCase):
    def test_value(self):
        parsed = parse_json(b'{"a": [1, 2.0, true, null]}')
        self.assertEqual(
            parsed, Parsed(parser="json", encoding="utf-8", value={"a": [1, 2.0, True, None]})
        )

    def test_top_level_scalar(self):
        self.assertEqual(parse_json(b'"just a string"').value, "just a string")

    def test_json_with_one_value_per_line_is_jsonl(self):
        parsed = parse_json(b'{"a": 1}\n\n{"a": 2}\n')
        self.assertEqual(parsed.parser, "jsonl")
        self.assertEqual(rows(parsed), [{"a": 1}, {"a": 2}])

    def test_invalid_json(self):
        for data in [b"{", b"{\n", b'{"a": 1}\n{oops}\n', b"NaN"]:
            with self.subTest(data=data), self.assertRaises(ParseError):
                parse_json(data)

    def test_jsonl_is_lazy(self):
        parsed = parse_json_lines(b'{"a": 1}\n{oops}\n')
        assert parsed.items is not None
        items = iter(parsed.items)
        self.assertEqual(next(items), {"a": 1})
        with self.assertRaises(ParseError):
            next(items)

    def test_js_json(self):
        cases = {
            b'window.YTD.tweets.part0 = [{"id": 1}]': ("window.YTD.tweets.part0 =", [{"id": 1}]),
            b'  var data = {"a": 1};\n': ("var data =", {"a": 1}),
            b"window['x'] = 3": ("window['x'] =", 3),
        }
        for data, (wrapper, value) in cases.items():
            with self.subTest(data=data):
                parsed = parse_js_json(data)
                self.assertEqual(
                    (parsed.parser, parsed.wrapper, parsed.value), ("js-json", wrapper, value)
                )

    def test_js_without_assignment(self):
        for data in [b"console.log(1)", b"x = {broken"]:
            with self.subTest(data=data), self.assertRaises(ParseError):
                parse_js_json(data)


class CsvTests(TestCase):
    def test_inference(self):
        cases = {
            "42": 42,
            "-7": -7,
            "0": 0,
            "3.14": 3.14,
            "-0.5": -0.5,
            ".5": 0.5,
            "1e5": 1e5,
            "true": True,
            "FALSE": False,
            "007": "007",
            "+41 44 123": "+41 44 123",
            "": "",
            "-": "-",
            "1.": "1.",
            "yes": "yes",
        }
        for cell, value in cases.items():
            with self.subTest(cell=cell):
                self.assertEqual(infer(cell), value)
                self.assertIs(type(infer(cell)), type(value))

    def test_header_cleanup(self):
        self.assertEqual(
            clean_header(["a", "", "a", " b ", "a"]), ["a", "column_2", "a_2", "b", "a_3"]
        )

    def test_semicolon_dialect_is_sniffed(self):
        parsed = parse_csv(b'name;note\nAnna;"a;b"\nBen;c\n')
        self.assertEqual(parsed.csv, CsvInfo(delimiter=";", quotechar='"'))
        self.assertEqual(
            rows(parsed), [{"name": "Anna", "note": "a;b"}, {"name": "Ben", "note": "c"}]
        )

    def test_short_long_and_blank_rows(self):
        parsed = parse_csv(b"a,b\r\n1\r\n\r\n1,2,3\r\n")
        self.assertEqual(rows(parsed), [{"a": 1}, {"a": 1, "b": 2, "column_3": 3}])

    def test_header_only_and_empty(self):
        self.assertEqual(rows(parse_csv(b"a,b\n")), [])
        self.assertEqual(rows(parse_csv(b"")), [])

    def test_legacy_encoding(self):
        parsed = parse_csv("Stadt,Land\nZürich,Schweiz\nGenève,Suisse\n".encode("cp1252"))
        self.assertEqual(parsed.encoding, "cp1252")
        self.assertEqual(rows(parsed)[1], {"Stadt": "Genève", "Land": "Suisse"})

    def test_malformed_csv_is_a_parse_error(self):
        huge = b'"' + b"x" * 200_000 + b'"'  # over the csv module's field size limit
        with self.assertRaises(ParseError):
            parse_csv(huge + b"\n1\n")
        with self.assertRaises(ParseError):
            rows(parse_csv(b"a\n" + huge + b"\n"))
