import io
import zipfile
from unittest import TestCase

from ddp_parser import is_data_point, is_structure, parse, suggest, walk


def root(members: dict[str, bytes]):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return parse(buffer.getvalue(), name="export.zip").root


def pairs(suggestions):
    return {
        path: [(c.path, c.reason, c.score) for c in found] for path, found in suggestions.items()
    }


class SuggestTests(TestCase):
    def test_known_paths_need_no_suggestion(self):
        tree = root({"a.json": b'{"k": 1}'})
        self.assertEqual(suggest(tree, tree), {})

    def test_moved_folder_maps_every_data_point(self):
        known = root(
            {
                "activity/watch.json": b'{"url": "https://x.y", "at": "2024-01-01"}',
                "readme.json": b"{}",
            }
        )
        new = root(
            {
                "your_activity/activity/watch.json": b'{"url": "https://x.y", "at": "2024-01-02"}',
                "readme.json": b"{}",
            }
        )
        self.assertEqual(
            pairs(suggest(known, new)),
            {
                "/your_activity/activity/watch.json/url": [
                    ("/activity/watch.json/url", "moved", 1.0)
                ],
                "/your_activity/activity/watch.json/at": [
                    ("/activity/watch.json/at", "moved", 1.0)
                ],
            },
        )

    def test_renamed_key_inside_a_moved_folder(self):
        known = {
            "activity/watch.json": b'{"Date": "2024-01-01", "url": "https://x.y"}',
            "r.json": b"{}",
        }
        new = {
            "new/activity/watch.json": b'{"Datum": "2024-01-02", "url": "https://x.y"}',
            "r.json": b"{}",
        }
        found = pairs(suggest(root(known), root(new)))
        self.assertEqual(
            found["/new/activity/watch.json/Datum"], [("/activity/watch.json/Date", "renamed", 1.0)]
        )

    def test_renamed_key(self):
        known = root({"a.json": b'{"x": 1, "user": {"email": "a@b.ch"}}'})
        new = root({"a.json": b'{"x": 1, "user": {"mail": "c@d.ch"}}'})
        found = pairs(suggest(known, new))
        self.assertEqual(found["/a.json/user/mail"], [("/a.json/user/email", "renamed", 0.9)])

    def test_translated_keys_rank_by_position_and_format(self):
        known = root({"a.json": b'[{"Date": "2024-01-01", "Title": "Hello world"}]'})
        new = root({"a.json": b'[{"Datum": "2024-02-02", "Titel": "Hallo Welt"}]'})
        found = pairs(suggest(known, new))
        self.assertEqual(found["/a.json/[]/Datum"], [("/a.json/[]/Date", "renamed", 1.0)])
        self.assertEqual(found["/a.json/[]/Titel"], [("/a.json/[]/Title", "renamed", 0.9)])

    def test_renamed_list_carries_its_items(self):
        known = root(
            {
                "a.json": b'{"watched_videos": [{"url": "https://x.y/1", "at": "2024-01-01"}], "n": 1}'
            }
        )
        new = root(
            {
                "a.json": b'{"videos_watched": [{"url": "https://x.y/2", "at": "2024-01-02"}], "n": 2}'
            }
        )
        found = pairs(suggest(known, new))
        self.assertEqual(
            found["/a.json/videos_watched"], [("/a.json/watched_videos", "renamed", 1.0)]
        )
        self.assertEqual(
            found["/a.json/videos_watched/[]/url"],
            [("/a.json/watched_videos/[]/url", "moved", 1.0)],
        )

    def test_translated_object_and_its_keys(self):
        known = root({"a.json": b'{"Comments": {"Date": "2024-01-01", "Text": "hi you"}, "n": 1}'})
        new = root(
            {"a.json": b'{"Kommentare": {"Datum": "2024-01-02", "Text": "hallo du"}, "n": 1}'}
        )
        found = pairs(suggest(known, new))
        # the object only groups keys, so it isn't offered, but it is followed: half of its
        # sub-paths match ("", /Text vs /Date, /Datum), so it is renamed with 0.5 + 0.3 + 0.2 * 0.5
        self.assertNotIn("/a.json/Kommentare", found)
        # "Text" is found as a move on its own (same name, unique on both sides): certain
        self.assertEqual(
            found["/a.json/Kommentare/Text"], [("/a.json/Comments/Text", "moved", 1.0)]
        )
        # "Datum" needs the rename of its object, so it is only as sure as that rename
        self.assertEqual(
            found["/a.json/Kommentare/Datum"], [("/a.json/Comments/Date", "renamed", 0.9)]
        )

    def test_renamed_file_carries_its_content_but_is_not_offered(self):
        known = root(
            {"comments.json": b'{"Date": "2024-01-01", "Text": "hi you"}', "r.json": b"{}"}
        )
        new = root(
            {"kommentare.json": b'{"Datum": "2024-01-02", "Text": "hallo du"}', "r.json": b"{}"}
        )
        found = pairs(suggest(known, new))
        self.assertNotIn("/kommentare.json", found)  # a file is not a data point
        self.assertEqual(found["/kommentare.json/Datum"][0][:2], ("/comments.json/Date", "renamed"))

    def test_different_contents_are_no_rename(self):
        known = root({"a.json": b'{"history": [{"a": 1, "b": 2, "c": 3}], "n": 1}'})
        new = root({"a.json": b'{"orders": [{"x": 1, "y": 2, "z": 3}], "n": 1}'})
        self.assertNotIn("/a.json/orders", suggest(known, new))

    def test_empty_list_renamed(self):
        known = root({"a.json": b'{"CoinPurchaseHistoryList": [], "n": 1}'})
        new = root({"a.json": b'{"MuenzkaufListe": [], "n": 1}'})
        found = pairs(suggest(known, new))
        self.assertEqual(
            found["/a.json/MuenzkaufListe"], [("/a.json/CoinPurchaseHistoryList", "renamed", 1.0)]
        )

    def test_ambiguous_objects_are_not_followed(self):
        known = root({"a.json": b'{"p": {"k": "x"}, "q": {"k": "x"}}'})
        new = root({"a.json": b'{"m": 1, "n": 2, "r": {"k": "x"}}'})  # r matches neither position
        found = pairs(suggest(known, new))
        # r fits p and q equally well (0.7 each), so it isn't followed, and its key isn't mapped
        self.assertNotIn("/a.json/r/k", found)

    def test_several_candidates_are_ranked(self):
        known = root({"a.json": b'{"x": "abc", "y": "def"}'})
        new = root({"a.json": b'{"p": "ghi", "q": "jkl"}'})
        found = pairs(suggest(known, new))
        self.assertEqual([c[0] for c in found["/a.json/p"]], ["/a.json/x", "/a.json/y"])
        self.assertEqual([c[0] for c in found["/a.json/q"]], ["/a.json/y", "/a.json/x"])

    def test_no_candidate_when_known_siblings_are_still_there_or_differ(self):
        known = root({"a.json": b'{"x": "abc", "n": 5}'})
        new = root({"a.json": b'{"x": "abc", "added": "def", "count": "2024-01-01"}'})
        self.assertEqual(suggest(known, new), {})

    def test_new_file_without_known_parent(self):
        found = pairs(suggest(root({"a.json": b"{}"}), root({"b/c.json": b'{"k": 1}'})))
        self.assertEqual(found, {})


class NodeClassTests(TestCase):
    def test_data_points_and_structures(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
        tree = root(
            {
                "a.json": b'{"emails": [], "o": {}, "s": "x", "mixed": [1], '
                b'"rows": [{"user": {"name": "A"}, "at": 1}], "maybe": {"k": 1}}',
                "b.json": b'"just text"',
                "list.json": b'[{"at": 1}]',
                "rows.csv": b"a,b\n1,2\n",
                "d/photo.png": png,
                "d/p.bin": b"x",
            }
        )
        nodes = {node.path: node for node in walk(tree)}
        data_points = [
            "/a.json/emails",  # a list (even empty)
            "/a.json/s",  # a value
            "/a.json/rows",  # a list
            "/a.json/rows/[]",  # its item: the entity (an object)
            "/a.json/mixed/[]",  # an item that is a value
            "/a.json/rows/[]/at",  # a field of the items
            "/a.json/rows/[]/user/name",
            "/d/photo.png",  # media
            "/list.json",  # a file that is a list
            "/rows.csv",  # a CSV: a list of rows
            "/list.json/[]",
            "/list.json/[]/at",
        ]
        not_data_points = [
            "",  # the root
            "/d",  # a folder
            "/a.json",  # a parsed file
            "/b.json",  # a parsed file holding a single value
            "/d/p.bin",  # an unmatched file
            "/a.json/o",  # an object that only groups keys
            "/a.json/maybe",
            "/a.json/rows/[]/user",  # an object inside an item, not an item itself
        ]
        for path in data_points:
            with self.subTest(path=path):
                self.assertTrue(is_data_point(nodes[path]))
        for path in not_data_points:
            with self.subTest(path=path):
                self.assertFalse(is_data_point(nodes[path]))
        self.assertTrue(is_structure(nodes["/a.json/o"]))
        self.assertFalse(is_structure(nodes["/a.json/s"]))
        self.assertFalse(is_structure(nodes["/d/photo.png"]))  # a file, not parsed content
