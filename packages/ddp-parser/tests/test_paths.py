from unittest import TestCase

from ddp_parser.errors import InvalidPathError
from ddp_parser.model.paths import ITEMS, ROOT, escape, join, split, unescape

SPEC_EXAMPLE = "/messages/inbox/chat_1/message_1.json/messages/[]/sender_name"
SPEC_SEGMENTS = ["messages", "inbox", "chat_1", "message_1.json", "messages", "[]", "sender_name"]

TRICKY_NAMES = ["~", "~0", "~1", "a/b", "/", "#", "[]", "{n}", "", " ", "ä/ö#ü", "~/~/"]


class PathTests(TestCase):
    def test_spec_example(self):
        path = ROOT
        for name in SPEC_SEGMENTS:
            path = join(path, name)
        self.assertEqual(path, SPEC_EXAMPLE)
        self.assertEqual(split(SPEC_EXAMPLE), SPEC_SEGMENTS)

    def test_items_marker(self):
        self.assertEqual(join("/posts.json", ITEMS), "/posts.json/[]")

    def test_root(self):
        self.assertEqual(split(ROOT), [])

    def test_escape_order_follows_rfc_6901(self):
        self.assertEqual(escape("~/"), "~0~1")
        self.assertEqual(escape("~1"), "~01")
        self.assertEqual(unescape("~01"), "~1")

    def test_round_trip_tricky_names(self):
        for name in TRICKY_NAMES:
            with self.subTest(name=name):
                self.assertEqual(split(join(join(ROOT, name), name)), [name, name])

    def test_invalid_paths(self):
        for bad in ["a", "/a~2", "/a~", "/~~01"]:
            with self.subTest(path=bad), self.assertRaises(InvalidPathError):
                split(bad)
