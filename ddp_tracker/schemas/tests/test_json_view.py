from datetime import date
from textwrap import dedent

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.filters import SchemaFilter
from ddp_tracker.schemas.json_view import json_path
from ddp_tracker.schemas.models import Location, Observation

FIRST = (
    b'{"Your Activity": {"Watch History": {"VideoList": [{"Date": "2024-01-01 10:00:00", '
    b'"Link": "https://x.y/1", "Title": ""}]}}, "Ids": [1, 2], "Group Chat": {"GroupChat": {}}}'
)
SECOND = b'{"Your Activity": {"Watch History": {"VideoList": [{"Date": "2024-02-01 10:00:00"}]}}}'
HISTORY = "/user_data.json/Your Activity/Watch History"


class JsonPathTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            self.platform,
            {"user_data.json": FIRST, "comments.json": b'[{"text": "hi there"}]'},
            requested_at=date(2026, 1, 1),
            register=True,
        )
        parsed_upload(
            self.platform, {"user_data.json": SECOND}, requested_at=date(2026, 6, 1), register=True
        )

    def view(self, path, observations=None):
        return json_path(Location.objects.get(path=path), observations or Observation.objects.all())

    def test_your_example(self):
        expected = dedent(
            """\
            {
              "Your Activity": {
                "Watch History": {
                  "VideoList": [
                    {
                      "Date": <text · datetime>,
                      "Link": <text · url>,
                      "Title": <text · empty>
                    }
                  ]
                }
              }
            }"""
        )
        # the value, its item and its list all show the item's fields
        for path in ("/VideoList/[]/Date", "/VideoList/[]", "/VideoList"):
            with self.subTest(path=path):
                self.assertEqual(self.view(HISTORY + path), expected)

    def test_objects_show_their_keys(self):
        self.assertEqual(
            self.view(HISTORY),
            dedent(
                """\
                {
                  "Your Activity": {
                    "Watch History": {
                      "VideoList": […]
                    }
                  }
                }"""
            ),
        )
        # a top-level key of the file: the file's object, siblings abbreviated
        self.assertEqual(
            self.view("/user_data.json/Group Chat/GroupChat"),
            '{\n  "Group Chat": {\n    "GroupChat": {}\n  }\n}',
        )
        self.assertEqual(
            self.view("/user_data.json/Ids/[]"), '{\n  "Ids": [\n    <integer>\n  ]\n}'
        )
        self.assertEqual(self.view("/user_data.json/Ids"), '{\n  "Ids": [\n    <integer>\n  ]\n}')
        self.assertEqual(self.view("/comments.json/[]/text"), '[\n  {\n    "text": <text>\n  }\n]')
        self.assertEqual(self.view("/comments.json"), '[\n  {\n    "text": <text>\n  }\n]')
        self.assertEqual(
            self.view("/user_data.json"),
            '{\n  "Your Activity": {…},\n  "Ids": […],\n  "Group Chat": {…}\n}',
        )

    def test_follows_the_filter(self):
        later = SchemaFilter(requested_from=date(2026, 3, 1)).observations(self.platform)
        view = self.view(HISTORY + "/VideoList/[]/Date", later)
        self.assertIn('"Date": <text · datetime>\n', view)
        self.assertNotIn("Link", view)

    def test_nothing_outside_files(self):
        self.assertIsNone(self.view(""))

    def test_side_panel(self):
        url = reverse("schemas:location", args=["tiktok"])
        response = self.client.get(url, {"path": HISTORY + "/VideoList/[]/Date"})
        self.assertContains(response, "<summary>As JSON</summary>", html=True)
        self.assertContains(response, "&quot;Link&quot;: &lt;text · url&gt;")
        self.assertNotContains(self.client.get(url, {"path": ""}), "As JSON")
