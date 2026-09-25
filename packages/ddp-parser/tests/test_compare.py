import io
import zipfile
from unittest import TestCase

from ddp_parser import Status, compare, parse


def root(members: dict[str, bytes]):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return parse(buffer.getvalue(), name="export.zip").root


BASE = {
    "profile/profile.json": b'{"name": "A", "email": "a@b.ch", "joined": "2024-01-01"}',
    "posts/posts_1.json": b'[{"text": "hi", "ts": 1767225600}]',
    "posts/posts_2.json": b'[{"text": "yo", "ts": 1767225601}]',
}


class CompareTests(TestCase):
    def test_identical(self):
        self.assertTrue(compare(root(BASE), root(BASE)).is_empty)

    def test_counts_and_nulls_are_not_changes(self):
        other = {**BASE, "posts/posts_3.json": b'[{"text": null, "ts": 1767225602}]'}
        self.assertTrue(compare(root(BASE), root(other)).is_empty)

    def test_added_and_removed_report_subtree_tops(self):
        new = {k: v for k, v in BASE.items() if not k.startswith("posts/")}
        new["ads/advertisers.json"] = b'[{"name": "Acme"}]'
        result = compare(root(BASE), root(new))
        self.assertEqual(result.added, ("/ads",))
        self.assertEqual(result.removed, ("/posts",))
        self.assertEqual(result.status("/ads/advertisers.json/[]/name"), Status.ADDED)
        self.assertEqual(result.status("/posts/posts_{n}.json"), Status.REMOVED)
        self.assertEqual(result.status("/profile/profile.json"), Status.UNCHANGED)

    def test_moved_folder(self):
        new = {k.replace("profile/", "account/profile/"): v for k, v in BASE.items()}
        result = compare(root(BASE), root(new))
        self.assertEqual(
            [(m.old, m.new) for m in result.moved],
            [("/profile", "/account/profile")],
        )
        self.assertEqual(result.added, ("/account",))  # only the new folder itself
        self.assertEqual(result.removed, ())
        self.assertEqual(result.status("/profile/profile.json/email"), Status.MOVED_FROM)
        self.assertEqual(result.status("/account/profile/profile.json/email"), Status.MOVED_TO)

    def test_moved_key_inside_a_file(self):
        base = {"a.json": b'{"user": {"email": "a@b.ch"}, "meta": {}}'}
        new = {"a.json": b'{"user": {}, "meta": {"email": "a@b.ch"}}'}
        result = compare(root(base), root(new))
        self.assertEqual(
            [(m.old, m.new) for m in result.moved], [("/a.json/user/email", "/a.json/meta/email")]
        )

    def test_ambiguous_or_different_moves_stay_added_and_removed(self):
        base = {"a/x.json": b'{"k": 1}'}
        # a loose file keeps b/ and c/ from being collapsed into one {*} folder
        two_targets = {"b/x.json": b'{"k": 1}', "c/x.json": b'{"k": 1}', "readme.json": b"{}"}
        self.assertEqual(compare(root(base), root(two_targets)).moved, ())
        different = {"b/x.json": b'{"other": 1, "more": 2, "keys": 3}'}
        self.assertEqual(compare(root(base), root(different)).moved, ())

    def test_changes(self):
        base = {"a.json": b'{"n": 1, "d": "2024-01-01", "t": 1767225600, "m": "x"}'}
        new = {
            "a.json": b'{"n": "one", "d": "01.02.2024", "t": "2026-01-01T00:00:00Z", "m": "x y"}'
        }
        result = compare(root(base), root(new))
        changes = {change.path: change.fields for change in result.changed}
        self.assertEqual(changes["/a.json/n"], ("type", "shape"))
        self.assertEqual(changes["/a.json/d"], ("format",))
        self.assertEqual(changes["/a.json/t"], ("type", "shape", "format"))  # s → ISO string
        self.assertEqual(changes["/a.json/m"], ("shape",))  # alpha → text
        self.assertEqual(result.status("/a.json/n"), Status.CHANGED)

    def test_kind_change(self):
        result = compare(root({"a.json": b"{}"}), root({"a.json": b"{"}))
        self.assertEqual([c.fields for c in result.changed], [("kind",)])
