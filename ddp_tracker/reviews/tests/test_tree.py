"""The "To assign" tree (reviews/tree.py): files, groups, one row per list and item, rows below their
list, previews and the filter."""

import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.ddps.values import OwnValues
from ddp_tracker.reviews.services import review, triage_items
from ddp_tracker.reviews.tree import build, build_row
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.schemas.tree import CHAIN, places, row_key, sections, type_badge
from ddp_tracker.users.models import User

F = "/data.json"
DATA = {
    "Ads": {
        "Off": {"Events": [{"When": "2026-02-26 09:04:56", "Meta": {"Id": "a1"}}]},
        "Count": 3,
    },
    "Tags": ["x", "y"],
    "Nested": [{"Parts": [{"Name": "p"}]}],
    "Link": "https://example.com/a",
    "Maybe": None,
}


class TreeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        members = {"data.json": json.dumps(DATA).encode()}
        self.upload = parsed_upload(self.platform, members, register=True)

    def tree(self, own=None, q=""):
        return build(self.upload, triage_items(self.upload), own, q)

    def rows(self, tree=None):
        return {row.key: row for group in (tree or self.tree()).groups for row in group.lines()}

    def test_groups_are_key_chains_without_data_points(self):
        groups = {group.path: group for group in self.tree().groups}
        self.assertEqual(list(groups), [F + "/Ads/Off", F + "/Ads", F])  # in file order
        self.assertEqual(
            groups[F + "/Ads/Off"].crumbs,
            [("Ads", True), ("Off", True)],  # the file is the root
        )
        # "Count" comes after the nested "Off" in the file, and still is in the one "Ads" group
        self.assertEqual([row.key for row in groups[F + "/Ads"].rows], [F + "/Ads/Count"])

    def test_a_list_and_its_item_are_one_row_with_the_fields_below(self):
        rows = self.rows()
        events = rows[F + "/Ads/Off/Events"]
        self.assertTrue(events.is_list)
        self.assertEqual(events.name, "Events[]")
        self.assertEqual(events.primary.path, F + "/Ads/Off/Events/[]")  # the item's meaning
        self.assertNotIn(F + "/Ads/Off/Events/[]", rows)  # no row of its own
        when = rows[F + "/Ads/Off/Events/[]/When"]
        self.assertEqual((when.depth, when.name), (1, "When"))
        self.assertEqual(rows[F + "/Ads/Off/Events/[]/Meta/Id"].name, "Meta" + CHAIN + "Id")
        # lists in lists: one level deeper
        self.assertEqual(rows[F + "/Nested/[]/Parts"].depth, 1)
        self.assertEqual(rows[F + "/Nested/[]/Parts/[]/Name"].depth, 2)
        # a list of values is one row too
        self.assertEqual(rows[F + "/Tags"].locations[-1].path, F + "/Tags/[]")

    def test_decided_only_when_list_and_item_are(self):
        item = Location.objects.get(path=F + "/Tags/[]")
        create_annotation(item, "Tag", self.user)
        row, group, root = build_row(self.upload, Location.objects.get(path=F + "/Tags"))
        self.assertEqual((group, root), (F, F))
        self.assertFalse(row.decided)
        following = row.open_location
        assert following is not None
        self.assertEqual(following.path, F + "/Tags")  # the list is next
        create_annotation(following, "List of Tag", self.user)
        row, _, _ = build_row(self.upload, Location.objects.get(path=F + "/Tags"))
        self.assertTrue(row.decided)
        self.assertNotIn(F + "/Tags", self.rows())  # decided and nothing below: gone

    def test_annotated_rows_on_request(self):
        create_annotation(Location.objects.get(path=F + "/Link"), "Link", self.user)
        self.assertNotIn(F + "/Link", self.rows())
        rows = self.rows(build(self.upload, triage_items(self.upload), annotated=True))
        self.assertTrue(rows[F + "/Link"].decided)
        self.assertEqual(list(rows)[:2], [F + "/Ads/Off/Events", F + "/Ads/Off/Events/[]/When"])

    def test_a_decided_list_stays_above_its_open_fields(self):
        for path in (F + "/Ads/Off/Events", F + "/Ads/Off/Events/[]"):
            create_annotation(Location.objects.get(path=path), path.rsplit("/", 1)[-1], self.user)
        events = self.rows()[F + "/Ads/Off/Events"]
        self.assertTrue(events.decided)
        self.assertEqual(len(events.children), 2)  # When and Meta/Id
        off = next(g for g in self.tree().groups if g.path == F + "/Ads/Off")
        self.assertEqual(off.open_count, 2)

    def test_type_badges(self):
        rows = self.rows()
        self.assertEqual(rows[F + "/Ads/Off/Events"].type_badge, "array")
        self.assertEqual(rows[F + "/Ads/Off/Events/[]/When"].type_badge, "datetime")
        self.assertEqual(rows[F + "/Link"].type_badge, "url")
        self.assertEqual(rows[F + "/Ads/Count"].type_badge, "integer")
        maybe = rows[F + "/Maybe"].observation
        maybe.type = "null|string"
        maybe.shape = ""
        self.assertEqual(type_badge(maybe), "string?")

    def test_previews_are_the_uploaders_values_only(self):
        rows = self.rows()
        self.assertEqual(rows[F + "/Ads/Off/Events"].summary, "1 item")
        self.assertEqual(rows[F + "/Tags"].summary, "2 items")
        self.assertEqual(rows[F + "/Ads/Off/Events/[]/When"].summary, "%Y-%m-%d %H:%M:%S")
        self.assertEqual(rows[F + "/Link"].preview, [])  # nobody's values without them
        own = OwnValues({F + "/Tags/[]": ["x", "y", "z"], F + "/Link": [5]})
        rows = self.rows(self.tree(own))
        self.assertEqual((rows[F + "/Tags"].preview, rows[F + "/Tags"].more), (["x"], 2))
        self.assertEqual(rows[F + "/Link"].preview, ["5"])

    def test_the_filter(self):
        by_name = self.rows(self.tree(q="meta"))
        # a field matches: kept with its list, in its group
        self.assertEqual(set(by_name), {F + "/Ads/Off/Events", F + "/Ads/Off/Events/[]/Meta/Id"})
        by_list = self.rows(self.tree(q="events"))
        self.assertEqual(len(by_list), 3)  # the list, with everything below it
        self.assertEqual(self.tree(q="secret").groups, [])
        own = OwnValues({F + "/Link": ["https://secret.example"]})
        self.assertEqual(set(self.rows(self.tree(own, q="SECRET"))), {F + "/Link"})

    def test_only_where_to_start_is_open(self):
        tree = self.tree()
        self.assertEqual([root.is_open for root in tree.roots], [True])
        self.assertEqual([g.is_open for g in tree.groups], [True, False, False])  # Ads/Off first
        for path in (F + "/Ads/Off/Events", F + "/Ads/Off/Events/[]"):
            create_annotation(Location.objects.get(path=path), path.rsplit("/", 1)[-1], self.user)
        for path in (F + "/Ads/Off/Events/[]/When", F + "/Ads/Off/Events/[]/Meta/Id"):
            create_annotation(Location.objects.get(path=path), path.rsplit("/", 1)[-1], self.user)
        # Ads/Off is done: the next group with something to assign opens
        self.assertEqual([g.is_open for g in self.tree().groups], [True, False])
        # a filter's matches are all open
        filtered = self.tree(q="a")
        self.assertTrue(all(g.is_open for g in filtered.groups))
        self.assertTrue(all(r.is_open for r in filtered.roots))

    def test_row_keys_and_crumbs(self):
        self.assertEqual(row_key("/a/L/[]/[]"), "/a/L")
        self.assertEqual(row_key("/a/L/[]/x"), "/a/L/[]/x")
        found = places(self.platform.pk, [F + "/Nested/[]/Parts/[]", F, ""], "export.zip")
        nested = found[F + "/Nested/[]/Parts/[]"]
        self.assertEqual((nested.root, nested.title), (F, [("data.json", True)]))
        self.assertEqual(nested.crumbs, [("Nested[]", True), ("Parts[]", True)])
        self.assertEqual((found[F].root, found[F].crumbs), (F, []))  # directly in the file
        self.assertEqual((found[""].root, found[""].title), ("", [("export.zip", True)]))


class OrderTests(TestCase):
    def test_a_later_upload_keeps_the_file_order(self):
        platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            platform, {"a.json": b'{"B": {"x": 1}}'}, requested_at=date(2026, 1, 1), register=True
        )
        later = parsed_upload(
            platform,
            {"a.json": b'{"A": {"y": 1}, "B": {"x": 1}}'},
            requested_at=date(2026, 2, 1),
            register=True,
        )
        tree = build(later, triage_items(later))
        self.assertEqual([g.path for g in tree.groups], ["/a.json/A", "/a.json/B"])


class RootTests(TestCase):
    """One root per file; files that are data points themselves sit in their folder's root."""

    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def roots(self, upload):
        return {root.path: root for root in build(upload, triage_items(upload)).roots}

    def test_files_and_folders(self):
        upload = parsed_upload(
            self.platform,
            {
                "profile/profile.json": b'{"name": "Anna", "About": {"bio": "hi"}}',
                "activity/watch_history.json": b'[{"Date": "2026-01-01"}]',
                "photos/p.png": b"\x89PNG\r\n\x1a\n",
            },
            register=True,
        )
        roots = self.roots(upload)
        self.assertEqual(list(roots), ["/activity", "/photos", "/profile/profile.json"])
        profile = roots["/profile/profile.json"]
        self.assertEqual(profile.title, [("profile", False), ("profile.json", True)])
        # the file's own keys: no group heading; a key chain: one
        self.assertEqual([g.crumbs for g in profile.groups], [[], [("About", True)]])
        self.assertEqual(profile.open_count, 2)
        activity = roots["/activity"]
        self.assertEqual(activity.title, [("activity/", True)])  # a folder
        (group,) = activity.groups
        self.assertEqual(
            [row.key for row in group.lines()],
            ["/activity/watch_history.json", "/activity/watch_history.json/[]/Date"],
        )
        self.assertEqual(roots["/photos"].title, [("photos/", True)])

    def test_a_single_file_upload(self):
        upload = parsed_file(self.platform, "posts.json", b'{"a": {"b": 1}, "c": 2}', register=True)
        (root,) = self.roots(upload).values()
        self.assertEqual((root.path, root.title), ("", [("posts.json", True)]))
        self.assertEqual([g.crumbs for g in root.groups], [[("a", True)], []])


class MissingRootTests(TestCase):
    """The Missing tab's locations come from other uploads, of other formats too: a single
    file's keys are one root with groups, like a zip's file, not a root per group."""

    def test_missing_keys_of_a_single_file_and_a_zip(self):
        user = User.objects.create_user("curator")
        platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            platform,
            {"user_data.json": b'{"Profile": {"name": "A"}, "Ads": {"Off": {"x": 1}}}'},
            requested_at=date(2026, 1, 1),
            register=True,
        )
        parsed_file(platform, "posts.json", b'{"Posts": {"title": "t"}, "n": 1}', register=True)
        for path in (
            "/user_data.json/Profile/name",
            "/user_data.json/Ads/Off/x",
            "/Posts/title",
            "/n",
        ):
            create_annotation(Location.objects.get(path=path), path.rsplit("/", 1)[-1], user)
        later = parsed_upload(
            platform,
            {"user_data.json": b'{"Other": 1}'},
            requested_at=date(2026, 3, 1),
            register=True,
        )
        entries = [(m.location, m) for m in review(later).missing]
        roots = {r.path: r for r in sections(platform.pk, entries, "Single-file uploads")}
        self.assertEqual(set(roots), {"", "/user_data.json"})
        single = roots[""]
        self.assertEqual(single.title, [("Single-file uploads", True)])
        self.assertEqual(sorted(g.crumbs for g in single.groups), [[], [("Posts", True)]])
        self.assertEqual(
            sorted(g.crumbs for g in roots["/user_data.json"].groups),
            [[("Ads", True), ("Off", True)], [("Profile", True)]],
        )

    def test_the_missing_tab_names_single_file_keys(self):
        user = User.objects.create_user("curator")
        platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_file(platform, "posts.json", b'{"Posts": {"title": "t"}}', register=True)
        create_annotation(Location.objects.get(path="/Posts/title"), "title", user)
        later = parsed_upload(
            platform, {"a.json": b'{"x": 1}'}, requested_at=date(2026, 12, 1), register=True
        )
        self.client.force_login(user)
        page = self.client.get(reverse("reviews:review", args=[later.pk]), {"tab": "missing"})
        self.assertContains(page, "<strong>Single-file uploads</strong>", html=True)
        self.assertContains(page, '<details class="review-root" open>', count=1)
