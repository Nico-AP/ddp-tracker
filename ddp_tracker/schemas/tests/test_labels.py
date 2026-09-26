from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.filters import SchemaFilter
from ddp_tracker.schemas.labels import plain_type
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.services import review
from ddp_tracker.users.models import User


class PlainTypeTests(TestCase):
    def test_labels(self):
        cases = [
            # (kind, type, path, item type) → label
            (("data", "array", "/a.json/VideoList", "object"), "list of objects"),
            (("data", "array", "/a.json/Ids", "integer"), "list of integers"),
            (("data", "array", "/a.json/x", "object|string"), "list of objects or texts"),
            (("data", "array", "/a.json/x", "null|boolean"), "list of true/false values"),
            (("data", "array", "/a.json/x", ""), "list (always empty so far)"),
            (("data", "array|null", "/a.json/x", "number"), "list of numbers (or empty)"),
            (("data", "array|string", "/a.json/x", "integer"), "list of integers or text"),
            (("data", "object", "/a.json/VideoList/[]", ""), "object"),
            (("data", "integer", "/a.json/Ids/[]", ""), "integer"),
            (("data", "array", "/a.json/m/[]", "integer"), "list of integers"),
            (("data", "object", "/a.json/profile", ""), "group of keys"),
            (("data", "null|object", "/a.json/profile", ""), "group of keys (or empty)"),
            (("data", "string", "/a.json/x", ""), "text"),
            (("data", "null|string", "/a.json/x", ""), "text (or empty)"),
            (("data", "boolean", "/a.json/x", ""), "true/false"),
            (("data", "null", "/a.json/x", ""), "empty"),
            (("file", "array", "/comments.json", "object"), "file: list of objects"),
            (("file", "object", "/profile.json", ""), "file: group of keys"),
            (("file", "string", "/a.txt", ""), "file: text"),
            (("file", "", "/a.json", ""), "file"),
            (("folder", "", "/activity", ""), "folder"),
            (("container", "", "", ""), "archive"),
            (("media", "", "/p.png", ""), "media file"),
            (("unmatched", "", "/p.bin", ""), "unreadable file"),
        ]
        for args, label in cases:
            with self.subTest(args=args):
                self.assertEqual(plain_type(*args), label)

    def test_objects_always_seen_empty(self):
        cases = [
            (
                ("data", "object", "/a.json/Group Chat/GroupChat"),
                "group of keys (always empty so far)",
            ),
            (("data", "null|object", "/a.json/x"), "group of keys (always empty so far)"),
            (("data", "object", "/a.json/rows/[]"), "object (always empty so far)"),
            (("file", "object", "/empty.json"), "file: group of keys (always empty so far)"),
            (("data", "string", "/a.json/x"), "text"),  # values have no keys anyway
        ]
        for args, label in cases:
            with self.subTest(args=args):
                self.assertEqual(plain_type(*args, empty=True), label)


class LabelledPagesTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.upload = parsed_upload(
            self.platform,
            {
                "data.json": b'{"Watch History": {"VideoList": [{"Date": "2024-01-01", '
                b'"Link": "https://x.y/1"}]}, "Ids": [1, 2, 3], "Empty": [], '
                b'"profile": {"name": "Anna"}}',
                "comments.json": b'[{"text": "hi there"}]',
                "chats.json": b'{"Group Chat": {"GroupChat": {}}}',
            },
            requested_at=date(2026, 1, 1),
            register=True,
        )

    def labels(self, observations=None):
        locations = {location.path: location.pk for location in Location.objects.all()}
        found = profiles(locations.values(), observations or Observation.objects.all())
        return {path: found[pk].label for path, pk in locations.items()}

    def test_profiles_know_what_lists_hold(self):
        labels = self.labels()
        self.assertEqual(labels["/data.json/Watch History/VideoList"], "list of objects")
        self.assertEqual(labels["/data.json/Watch History/VideoList/[]"], "object")
        self.assertEqual(labels["/data.json/Watch History/VideoList/[]/Date"], "text")
        self.assertEqual(labels["/data.json/Ids"], "list of integers")
        self.assertEqual(labels["/data.json/Empty"], "list (always empty so far)")
        self.assertEqual(labels["/data.json/profile"], "group of keys")
        self.assertEqual(labels["/comments.json"], "file: list of objects")
        self.assertEqual(labels["/data.json"], "file: group of keys")
        self.assertEqual(labels["/chats.json/Group Chat"], "group of keys")
        self.assertEqual(
            labels["/chats.json/Group Chat/GroupChat"], "group of keys (always empty so far)"
        )
        # a later export with strings: counted per upload, within the filter's scope
        parsed_upload(
            self.platform,
            {"data.json": b'{"Ids": ["a", "b"]}'},
            requested_at=date(2026, 6, 1),
            register=True,
        )
        later = SchemaFilter(requested_from=date(2026, 3, 1)).observations(self.platform)
        self.assertEqual(self.labels(later)["/data.json/Ids"], "list of texts")

    def test_pages_show_labels(self):
        detail = reverse("schemas:location", args=["tiktok"])
        response = self.client.get(detail, {"path": "/data.json/Watch History/VideoList"})
        self.assertContains(response, "<h3>Details</h3>", html=True)
        self.assertContains(response, "<dt>Summary</dt>", html=True)
        self.assertContains(response, "<dd>List of objects</dd>", html=True)
        children = self.client.get(
            reverse("schemas:children", args=["tiktok"]),
            {"path": "/data.json/Watch History/VideoList"},
        )
        self.assertContains(children, "&lt;item&gt;")
        self.assertContains(children, ">object<", html=False)
        # a review row: from this upload's observations
        items = {item.location.path: item.item_type for item in review(self.upload).triage}
        self.assertEqual(items["/data.json/Ids"], "integer")
        self.client.force_login(User.objects.create_user("curator"))
        page = self.client.get(reverse("schemas:review", args=[self.upload.pk]))
        self.assertContains(page, "list of integers")
        row = self.client.get(
            reverse("schemas:triage-row", args=[Location.objects.get(path="/data.json/Ids").pk]),
            {"upload": self.upload.pk},
        )
        self.assertContains(row, "list of integers")

    def test_tree_labels_stay_short(self):
        children = self.client.get(
            reverse("schemas:children", args=["tiktok"]),
            {"path": "/data.json/Watch History/VideoList/[]"},
        )
        self.assertContains(children, '<span class="tree__shape">date</span>', html=True)
        self.assertNotContains(children, "%Y")  # formats: in the side panel
        self.assertNotContains(children, "tree__presence")  # upload counts: in the side panel
        ids = self.client.get(reverse("schemas:children", args=["tiktok"]), {"path": "/data.json"})
        self.assertNotContains(ids, '<span class="tree__shape">plain</span>', html=True)
