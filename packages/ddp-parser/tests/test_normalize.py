import json
from unittest import TestCase

import msgspec

from ddp_parser import Options, normalize, parse, renormalize
from ddp_parser.model import (
    SPEC_VERSION,
    ContainerNode,
    DataNode,
    FileNode,
    FolderNode,
    JsonType,
    MediaNode,
    Stats,
    walk,
)
from ddp_parser.normalize import is_variable_key
from tests.test_pipeline import PNG, make_zip

NAME = "user_data_tiktok.json"


def chat(*messages: str) -> list[dict]:
    return [{"Date": "2026-01-02 10:00:00", "From": "someone", "Content": m} for m in messages]


def document(data: dict, options: Options | None = None):
    """The parsed zip ``{NAME: data}``: its file node and warnings."""
    parsed = parse(make_zip({NAME: json.dumps(data).encode()}), options, name="export.zip")
    assert isinstance(parsed.root, ContainerNode)
    (file,) = parsed.root.children
    assert isinstance(file, FileNode)
    return file, parsed.warnings


def paths(node) -> set[str]:
    prefix = f"/{NAME}"
    return {n.path[len(prefix) :] for n in walk(node)}


def at(node, path: str):
    return next(n for n in walk(node) if n.path == f"/{NAME}{path}")


class KeyShapeTests(TestCase):
    def test_variable_shapes(self):
        for key in [
            "7637478253594217238",
            "12",
            "2024-01-03",
            "2024-01-03 10:00:00",
            "12:30",
            "anna@example.com",
            "https://example.com",
            "0b7a1f7e-3c4d-4e5f-8a9b-0c1d2e3f4a5b",
            "ab12cd34ef56gh78ij",
        ]:
            with self.subTest(key=key):
                self.assertTrue(is_variable_key(key))

    def test_field_names(self):
        for key in ["Date", "IP", "GAID", "ItemFavoriteList", "Chat History", "v2", "user_id"]:
            with self.subTest(key=key):
                self.assertFalse(is_variable_key(key))

    def test_id_keys_are_merged(self):
        watched = {
            "WatchLiveMap": {
                "7637478253594217238": {"Questions": [{"Q": "hi"}], "WatchTime": "5"},
                "7637478253594217239": {"WatchTime": "7"},
            }
        }
        file, _ = document({"Tiktok Live": watched})
        found = paths(file)
        self.assertIn("/Tiktok Live/WatchLiveMap/{*}/Questions", found)
        self.assertIn("/Tiktok Live/WatchLiveMap/{*}/Questions/[]/Q", found)
        self.assertFalse(any("763747" in path for path in found))
        merged = at(file, "/Tiktok Live/WatchLiveMap/{*}")
        self.assertEqual((merged.name, merged.keys), ("0", 2))
        self.assertEqual(merged.stats, Stats(count=2, present=2))
        # a key only one of them had is optional
        self.assertEqual(at(file, "/Tiktok Live/WatchLiveMap/{*}/Questions").stats.present, 1)

    def test_a_single_id_key(self):
        file, _ = document({"Map": {"7637478253594217238": {"a": 1}}})
        self.assertEqual(at(file, "/Map/{*}").keys, 1)


class SharedWordsTests(TestCase):
    def test_last_word(self):
        history = {
            "Chat History with bella.marry469": chat("hi", "there"),
            "Chat History with tom_99": chat("yo"),
        }
        file, _ = document({"ChatHistory": history})
        self.assertEqual(
            paths(file) - {"", "/ChatHistory"},
            {
                "/ChatHistory/Chat History with {*}",
                "/ChatHistory/Chat History with {*}/[]",
                "/ChatHistory/Chat History with {*}/[]/Date",
                "/ChatHistory/Chat History with {*}/[]/From",
                "/ChatHistory/Chat History with {*}/[]/Content",
            },
        )
        merged = at(file, "/ChatHistory/Chat History with {*}")
        self.assertEqual((merged.name, merged.keys), ("Chat History with xs0", 2))

    def test_first_word(self):
        file, _ = document({"a": {"anna's chats": chat("hi"), "tom's chats": chat("yo")}})
        self.assertIn("/a/{*} chats", paths(file))

    def test_different_insides_are_kept(self):
        activity = {
            "Favorite Videos": {"FavoriteVideoList": [{"Link": "x"}]},
            "Favorite Sounds": {"FavoriteSoundList": [{"Link": "x"}]},
        }
        file, _ = document({"Your Activity": activity})
        self.assertIn("/Your Activity/Favorite Videos/FavoriteVideoList", paths(file))

    def test_single_values_are_kept(self):
        settings = {"Who Can Post Comments": "Everyone", "Who Can Post Videos": "Friends"}
        file, _ = document({"Settings": settings})
        self.assertIn("/Settings/Who Can Post Comments", paths(file))

    def test_a_single_key_is_kept(self):
        file, _ = document({"ChatHistory": {"Chat History with bella.marry469": chat("hi")}})
        self.assertIn("/ChatHistory/Chat History with bella.marry469", paths(file))


class LookAlikeTests(TestCase):
    PREFERENCES = {
        "l.2the.k.2the.s": {"FollowingMuteWords": ["a"], "Filter": "on"},
        "bella.marry469": {"FollowingMuteWords": [], "Filter": "off"},
        "tom_99": {"FollowingMuteWords": ["b"], "Filter": "on"},
    }

    def test_three_look_alike_values(self):
        file, _ = document({"Family Content Preferences": self.PREFERENCES})
        self.assertEqual(
            paths(file) - {""},
            {
                "/Family Content Preferences",
                "/Family Content Preferences/{*}",
                "/Family Content Preferences/{*}/FollowingMuteWords",
                "/Family Content Preferences/{*}/FollowingMuteWords/[]",
                "/Family Content Preferences/{*}/Filter",
            },
        )
        self.assertEqual(at(file, "/Family Content Preferences/{*}").keys, 3)

    def test_two_are_not_enough(self):
        two = dict(list(self.PREFERENCES.items())[:2])
        file, _ = document({"Family Content Preferences": two})
        self.assertIn("/Family Content Preferences/bella.marry469", paths(file))

    def test_sections_that_differ_are_kept(self):
        sections = {
            "Profile": {"ProfileMap": {"userName": "x"}},
            "Comment": {"Comments": {"CommentsList": []}},
            "Post": {"VideoList": [{"Date": "x"}]},
        }
        file, _ = document(sections)
        self.assertIn("/Profile/ProfileMap/userName", paths(file))


class RuleTests(TestCase):
    SETTINGS = {"SettingsMap": {"Family Content Preferences": {"l.2the.k.2the.s": {"x": 1}}}}

    def test_variable_key_rule(self):
        rule = f"/{NAME}/SettingsMap/Family Content Preferences/*"
        file, _ = document(self.SETTINGS, Options(variable_keys=(rule,)))
        merged = at(file, "/SettingsMap/Family Content Preferences/{*}")
        self.assertEqual((merged.name, merged.keys), ("xs0xsxs0xsx", 1))
        self.assertIn("/SettingsMap/Family Content Preferences/{*}/x", paths(file))

    def test_rule_with_a_literal_part(self):
        rule = f"/{NAME}/ChatHistory/Chat History with *"
        data = {"ChatHistory": {"Chat History with bella.marry469": chat("hi")}}
        file, _ = document(data, Options(variable_keys=(rule,)))
        self.assertIn("/ChatHistory/Chat History with {*}/[]/Content", paths(file))

    def test_rule_with_several_wildcards_masks_the_whole_key(self):
        rule = f"/{NAME}/Chats/* with *"
        data = {"Chats": {"anna with tom": chat("hi")}}
        file, _ = document(data, Options(variable_keys=(rule,)))
        self.assertEqual(at(file, "/Chats/{*} with {*}").name, "xsxsx")

    def test_rules_see_renamed_parents(self):
        rule = f"/{NAME}/Map/{{*}}/*"
        data = {"Map": {"7637478253594217238": {"johndoe": {"a": 1}}}}
        file, _ = document(data, Options(variable_keys=(rule,)))
        self.assertIn("/Map/{*}/{*}/a", paths(file))

    def test_keep_key_rule(self):
        data = {"Years": {"2024": {"a": 1}, "2025": {"a": 2}}}
        file, _ = document(data, Options(keep_keys=(f"/{NAME}/Years/2024",)))
        self.assertEqual(
            {path for path in paths(file) if path.count("/") == 2},
            {"/Years/2024", "/Years/{*}"},
        )


class NormalizeTests(TestCase):
    DATA = {
        "WatchLiveMap": {"7637478253594217238": {"a": 1}, "7637478253594217239": {"a": 2}},
        "ChatHistory": {"Chat History with anna": chat("x"), "Chat History with tom": chat("y")},
    }

    def raw(self):
        """The tree without normalizing (a rule-free normalize is what parse() does)."""
        return parse(json.dumps(self.DATA).encode(), name=NAME).root

    def test_idempotent(self):
        rule = "/ChatHistory/Chat History with *"
        once = normalize(self.raw(), Options(variable_keys=(rule,))).root
        twice = normalize(once, Options(variable_keys=(rule,)))
        self.assertEqual(twice.root, once)
        self.assertEqual(twice.renames, {})

    def test_warning_paths_are_renamed(self):
        dates = {"7637478253594217238": "01/02/2026", "7637478253594217239": "03/04/2026"}
        _, warnings = document({"Map": dates})
        self.assertEqual(
            [(w.code, w.path) for w in warnings],
            [("ambiguous_date_order", f"/{NAME}/Map/{{*}}")],
        )


class RawTreeTests(TestCase):
    """``normalize`` on a tree that was never normalized (e.g. stored before spec 3.6)."""

    def test_renames_and_merged_stats(self):
        a = DataNode(name="a", path="/m/111/a", type=JsonType.INTEGER, stats=Stats(1, 1))
        b = DataNode(name="a", path="/m/222/a", type=JsonType.INTEGER, stats=Stats(1, 1))
        one = DataNode(
            name="111", path="/m/111", type=JsonType.OBJECT, stats=Stats(1, 1), properties={"a": a}
        )
        two = DataNode(
            name="222", path="/m/222", type=JsonType.OBJECT, stats=Stats(1, 1), properties={"a": b}
        )
        m = DataNode(
            name="m",
            path="/m",
            type=JsonType.OBJECT,
            stats=Stats(1, 1),
            properties={"111": one, "222": two},
        )
        file = FileNode(
            name="f.json",
            path="",
            parser="json",
            type=JsonType.OBJECT,
            stats=Stats(1, 1),
            properties={"m": m},
        )
        normalized = normalize(file, Options())
        self.assertEqual(
            normalized.renames,
            {
                "/m/111": "/m/{*}",
                "/m/111/a": "/m/{*}/a",
                "/m/222": "/m/{*}",
                "/m/222/a": "/m/{*}/a",
            },
        )
        merged = at_path(normalized.root, "/m/{*}/a")
        self.assertEqual(merged.stats, Stats(count=2, present=2))


def at_path(node, path: str):
    return next(n for n in walk(node) if n.path == path)


class RenormalizeTests(TestCase):
    """``renormalize`` on a stored document: wrapper folders lifted, rules applied later."""

    def stored(self):
        """A document parsed before its zip was known under the wrapper's name."""
        data = {"ChatHistory": {"Chat History with anna": chat("x")}}
        members = {
            "export-johndoe/": b"",
            f"export-johndoe/{NAME}": json.dumps(data).encode(),
            "__MACOSX/export-johndoe/._x": b"",
        }
        options = Options(keep_ignored=True)
        document = parse(make_zip(members), options, name="other.zip")
        root = msgspec.structs.replace(document.root, name="export-johndoe (1).zip")
        return msgspec.structs.replace(document, root=root)

    def test_lifts_the_wrapper_and_applies_rules(self):
        document = self.stored()
        rule = f"/{NAME}/ChatHistory/Chat History with *"
        result = renormalize(document, Options(variable_keys=(rule,)))
        new = {node.path for node in walk(result.document.root)}
        self.assertIn(f"/{NAME}/ChatHistory/Chat History with {{*}}/[]/Content", new)
        self.assertIn("/__MACOSX", new)  # OS junk stays where it was
        self.assertNotIn("/export-johndoe", new)
        self.assertEqual(result.renames["/export-johndoe"], "")
        self.assertEqual(
            result.renames[f"/export-johndoe/{NAME}/ChatHistory/Chat History with anna/[]"],
            f"/{NAME}/ChatHistory/Chat History with {{*}}/[]",
        )
        self.assertEqual(result.document.options["variable_keys"], [rule])
        self.assertEqual(result.document.spec_version, SPEC_VERSION)
        self.assertEqual(
            [(w.code, w.path) for w in result.document.warnings][-1:], [("wrapper_folder", None)]
        )

    def test_nothing_to_do(self):
        document = parse(json.dumps({"a": 1}).encode(), name=NAME)
        result = renormalize(document, Options())
        self.assertEqual(result.renames, {})
        self.assertEqual(result.document.root, document.root)

    def test_wrapper_named_differently_stays(self):
        document = self.stored()
        root = msgspec.structs.replace(document.root, name="takeout.zip")
        result = renormalize(msgspec.structs.replace(document, root=root), Options())
        self.assertEqual(result.renames, {})

    def test_nested_wrappers_and_warnings(self):
        inner = make_zip({"inner/a.json": b'{"7637478253594217238": {"x": 1}}'})
        document = parse(make_zip({"outer/inner.zip": inner}), name="x.zip")
        # stored as if parsed before wrappers were dropped, from a zip named "outer.zip"
        lifted = msgspec.structs.replace(document.root, name="outer.zip")
        result = renormalize(msgspec.structs.replace(document, root=lifted), Options())
        paths_after = {node.path for node in walk(result.document.root)}
        self.assertIn("/inner.zip/a.json/{*}/x", paths_after)

    def test_media_moves_with_the_wrapper(self):
        document = parse(make_zip({"export/photo.png": PNG}), name="x.zip")
        root = msgspec.structs.replace(document.root, name="export.zip")
        result = renormalize(msgspec.structs.replace(document, root=root), Options())
        self.assertEqual(result.renames["/export/{*}.png"], "/{*}.png")

    def test_a_single_file_is_no_wrapper(self):
        document = parse(make_zip({"export": b"{}"}), name="export.zip")
        self.assertEqual(renormalize(document, Options()).renames, {})


class MediaTests(TestCase):
    """Media file names are always replaced (spec 3.7)."""

    def root(self, members: dict[str, bytes]):
        return parse(make_zip(members), name="export.zip").root

    def media(self, root) -> dict[str, MediaNode]:
        return {node.path: node for node in walk(root) if isinstance(node, MediaNode)}

    def test_merged_per_extension(self):
        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\0" * 32
        root = self.root(
            {"m/johndoe_1.jpg": PNG, "m/anna.jpg": PNG + b"x", "m/clip.mp4": mp4, "m/a.png": PNG}
        )
        media = self.media(root)
        self.assertEqual(set(media), {"/m/{*}.jpg", "/m/{*}.mp4", "/m/{*}.png"})
        jpg = media["/m/{*}.jpg"]
        self.assertEqual((jpg.files, jpg.size_bytes), (2, 2 * len(PNG) + 1))
        self.assertIn(jpg.name, {"x.jpg", "xs0.jpg"})
        self.assertEqual(media["/m/{*}.mp4"].files, 1)

    def test_groups_and_single_files_merge(self):
        media = self.media(self.root({"IMG_1.JPG": PNG, "IMG_2.JPG": PNG, "x.jpg": PNG}))
        self.assertEqual(media["/{*}.jpg"].files, 3)

    def test_in_collapsed_folders_and_nested_zips(self):
        inner = make_zip({"p.png": PNG})
        root = self.root(
            {"inbox/anna_1/photos/a.png": PNG, "inbox/tom_2/photos/b.png": PNG, "in.zip": inner}
        )
        self.assertEqual(set(self.media(root)), {"/inbox/{*}/photos/{*}.png", "/in.zip/{*}.png"})

    def test_other_files_keep_their_names(self):
        root = self.root({"a.json": b"{}", "b.csv": b"a\n1\n", "notes.pdf": b"%PDF-1.4"})
        self.assertEqual(
            {node.path for node in walk(root)} - {""},
            {"/a.json", "/b.csv", "/b.csv/[]", "/b.csv/[]/a", "/notes.pdf"},
        )

    def test_renames_and_idempotency(self):
        # a document stored before spec 3.7: its media still under their own names
        photos = tuple(
            MediaNode(name=name, path=f"/d/{name}", ext=".png", size_bytes=size)
            for name, size in (("anna.png", 10), ("tom.png", 5))
        )
        root = ContainerNode(
            name="export.zip",
            path="",
            children=(FolderNode(name="d", path="/d", children=photos),),
        )
        stored = msgspec.structs.replace(parse(b"{}", name="a.json"), root=root)
        result = renormalize(stored, Options())
        self.assertEqual(result.renames, {"/d/anna.png": "/d/{*}.png", "/d/tom.png": "/d/{*}.png"})
        (merged,) = self.media(result.document.root).values()
        self.assertEqual((merged.name, merged.files, merged.size_bytes), ("x.png", 2, 15))
        again = renormalize(result.document, Options())
        self.assertEqual((again.renames, again.document.root), ({}, result.document.root))
