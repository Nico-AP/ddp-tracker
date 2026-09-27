"""The review page: one row per data point with a status that explains itself, tabs, and a side
panel in the context of the reviewed upload.
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation, review
from ddp_tracker.users.models import User

DATA = (
    b'{"Comment": {"Comments": {"App": [{"date": "2024-01-01", "comment": "hi there"}]}},'
    b' "Profile": {"name": "Anna"}}'
)
ZIPPED = {"user_data_tiktok.json": DATA}


class ReviewStatusTests(TestCase):
    """The same JSON file uploaded on its own, then inside a zip: every path moved."""

    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.single = parsed_file(self.platform, "user_data_tiktok.json", DATA, register=True)
        self.name = Location.objects.get(path="/Profile/name")
        create_annotation(self.name, "Display name", self.user)
        self.zipped = parsed_upload(
            self.platform, ZIPPED, requested_at=date(2026, 10, 1), register=True
        )

    def rows(self):
        return {item.location.path: item for item in review(self.zipped).triage}

    def test_moves_are_likely_moves_not_new_plus_missing(self):
        rows = self.rows()
        name = rows["/user_data_tiktok.json/Profile/name"]
        self.assertEqual(name.status, "moved")
        self.assertEqual(name.candidate["path"], "/Profile/name")
        self.assertEqual([c.annotation.name for c in name.choices], ["Display name"])
        # the old, annotated path is paired with its new row: not "missing" as well
        self.assertEqual(review(self.zipped).missing, [])
        # an old path without an annotation still explains the row
        date_row = rows["/user_data_tiktok.json/Comment/Comments/App/[]/date"]
        self.assertEqual(
            (date_row.status, date_row.candidate["path"], date_row.choices),
            ("moved", "/Comment/Comments/App/[]/date", []),
        )

    def test_new_and_seen_before(self):
        later = parsed_upload(
            self.platform,
            {"user_data_tiktok.json": DATA, "extra.json": b'{"flag": true}'},
            requested_at=date(2026, 11, 1),
            register=True,
        )
        rows = {item.location.path: item for item in review(later).triage}
        self.assertEqual(rows["/extra.json/flag"].status, "new")
        # in the earlier zip, never annotated: seen before (the earlier single file's paths don't
        # make it look moved: each format is its own reference)
        self.assertEqual(rows["/user_data_tiktok.json/Profile/name"].status, "seen")
        self.assertIsNone(rows["/user_data_tiktok.json/Profile/name"].candidate)

    def test_rows_are_in_file_order_and_item_fields_are_grouped(self):
        paths = list(self.rows())
        self.assertLess(
            paths.index("/user_data_tiktok.json/Comment/Comments/App"),
            paths.index("/user_data_tiktok.json/Profile/name"),
        )  # Comment comes first in the file
        groups = {path: item.group for path, item in self.rows().items()}
        app = "/user_data_tiktok.json/Comment/Comments/App"
        self.assertEqual(groups[app + "/[]/date"], app)
        self.assertEqual(groups[app + "/[]"], app)
        self.assertEqual(groups[app], "")
        # the list and its items' fields share one block (one stripe); others are their own
        blocks = {path: item.block for path, item in self.rows().items()}
        self.assertEqual({blocks[app], blocks[app + "/[]"], blocks[app + "/[]/date"]}, {app})
        name = "/user_data_tiktok.json/Profile/name"
        self.assertEqual(blocks[name], name)

    def test_page_tabs_and_rows(self):
        self.client.force_login(self.user)
        url = reverse("schemas:review", args=[self.zipped.pk])
        page = self.client.get(url)
        self.assertContains(page, "To assign (5)")
        self.assertContains(page, "Missing (0)")
        self.assertContains(page, "(likely matches")  # the reason, after the suggestion
        self.assertContains(page, ", not annotated)")  # a match without an annotation
        self.assertNotContains(page, "Compared with earlier")
        self.assertNotContains(page, "badge--type")  # no type tag in the review
        self.assertContains(page, "<code>/Profile/<wbr>name</code>")
        self.assertContains(page, "Use suggestion")
        self.assertContains(page, "Items of")
        self.assertContains(page, "Comments/<wbr>App[]</code>")
        self.assertContains(page, "&lt;item&gt;/<wbr><strong>date</strong>")  # below its list
        # labelled lines: what it is, what we think, what to do
        self.assertContains(page, "<dt>Annotation suggestion:</dt>", html=True)
        self.assertContains(self.client.get(url, {"tab": "missing"}), "Nothing missing")
        self.assertContains(self.client.get(url, {"tab": "nonsense"}), "To assign (5)")

    def test_use_suggestion_updates_the_row(self):
        self.client.force_login(self.user)
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        suggestion = review(self.zipped).triage
        chosen = next(item for item in suggestion if item.location == name).choices[0]
        response = self.client.post(
            reverse("schemas:triage", args=[name.pk]),
            {"action": "link", "annotation": chosen.annotation.pk, "upload": self.zipped.pk},
        )
        self.assertEqual(response["HX-Trigger"], f"triaged-{name.pk}")
        row = self.client.get(
            reverse("schemas:triage-row", args=[name.pk]), {"upload": self.zipped.pk}
        )
        self.assertContains(row, "<dt>Annotation:</dt>", html=True)
        self.assertContains(row, "review-item--annotated")  # shown in light green
        self.assertContains(row, "Display name")
        self.assertNotContains(row, "suggestion")
        self.assertNotContains(row, "Use suggestion")

    def test_side_panel_in_the_uploads_context(self):
        self.client.force_login(self.user)
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        panel = self.client.get(reverse("schemas:review-location", args=[self.zipped.pk, name.pk]))
        self.assertContains(panel, "<h3>Details</h3>", html=True)
        # the annotation block and its dialog know the upload (for the suggestions)
        self.assertContains(panel, f"upload={self.zipped.pk}")
        missing = self.client.get(
            reverse("schemas:review-location", args=[self.zipped.pk, self.name.pk])
        )
        self.assertContains(missing, "/Profile/name")  # not in this upload: all uploads


class ChangedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def test_changed_reads_was_and_now(self):
        parsed_upload(
            self.platform,
            {"a.json": b'{"when": "2024-01-01"}'},
            requested_at=date(2025, 1, 1),
            register=True,
        )
        later = parsed_upload(
            self.platform,
            {"a.json": b'{"when": "01.02.2024"}'},
            requested_at=date(2026, 1, 1),
            register=True,
        )
        (change,) = review(later).changed
        (diff,) = change.diffs
        self.assertEqual((diff.field, diff.before, diff.now), ("format", ("%Y-%m-%d",), "%d.%m.%Y"))
        self.client.force_login(self.user)
        page = self.client.get(reverse("schemas:review", args=[later.pk]), {"tab": "changed"})
        self.assertContains(page, "<code>%Y-%m-%d</code>", html=True)
        self.assertContains(page, "→ now")
        self.assertContains(page, "<code>%d.%m.%Y</code>", html=True)

    def test_a_kind_change_says_what_it_was(self):
        parsed_upload(
            self.platform, {"a.json": b'{"n": 1}'}, requested_at=date(2025, 1, 1), register=True
        )
        broken = parsed_upload(
            self.platform, {"a.json": b"{"}, requested_at=date(2026, 1, 1), register=True
        )
        diffs = {d.field: (d.before, d.now) for c in review(broken).changed for d in c.diffs}
        self.assertEqual(diffs["kind"], (("file",), "unmatched"))
        self.client.force_login(self.user)
        page = self.client.get(reverse("schemas:review", args=[broken.pk]), {"tab": "changed"})
        self.assertContains(page, "kind:")
        self.assertContains(page, "<code>unreadable file</code>", html=True)  # plain words
        self.assertNotContains(page, "(now )")
