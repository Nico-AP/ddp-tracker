"""The review page: one row per data point with a status that explains itself, tabs, and a side
panel in the context of the reviewed upload.
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.reviews.services import review
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
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

    def test_rows_are_in_file_order(self):
        paths = list(self.rows())
        self.assertLess(
            paths.index("/user_data_tiktok.json/Comment/Comments/App"),
            paths.index("/user_data_tiktok.json/Profile/name"),
        )  # Comment comes first in the file

    def test_page_tabs_groups_and_rows(self):
        self.client.force_login(self.user)
        url = reverse("reviews:review", args=[self.zipped.pk])
        page = self.client.get(url)
        # the list and its item are one row: App[], its fields date and comment, and name
        self.assertContains(page, 'id="open-count" class="badge rounded-pill">4<')
        self.assertContains(page, "Missing <span")
        self.assertContains(page, "not in this upload")
        self.assertContains(page, "Compared with earlier TikTok uploads")
        # groups: the key chains without data points, with how many rows are open
        self.assertContains(page, "<strong>user_data_tiktok.json</strong>", html=True, count=1)
        self.assertContains(page, '<span class="review-group__key">Comments</span>', html=True)
        self.assertContains(page, '<span class="muted">user_data_tiktok.json</span>', count=0)
        self.assertContains(page, "3 to assign")
        self.assertContains(page, "1 to assign")
        self.assertContains(page, "App[]")
        self.assertContains(page, "review-row--depth-1")  # the fields, below their list
        # one slot for every row's icon: [ ] a list, └ a field of its items, ◦ a value
        self.assertContains(
            page, '<span class="review-row__icon" aria-hidden="true">[ ]</span>', html=True
        )
        self.assertContains(
            page, '<span class="review-row__icon" aria-hidden="true">└</span>', html=True
        )
        self.assertContains(
            page, '<span class="review-row__icon" aria-hidden="true">◦</span>', html=True
        )
        # only where to start is expanded: the first file, and its first group
        self.assertContains(page, '<details class="review-root" open>', count=1)
        self.assertContains(page, '<details class="review-group" open>', count=1)
        self.assertContains(page, "Moved? Display name")  # the suggestion, as a pill
        self.assertNotContains(page, "Use suggestion")  # no buttons in rows: in the panel
        self.assertContains(page, "0 of 5 annotated")
        self.assertContains(
            page, '<div class="review-main" data-dialog-over>'
        )  # the dialog's place
        self.assertContains(self.client.get(url, {"tab": "missing"}), "Nothing missing")
        self.assertContains(self.client.get(url, {"tab": "nonsense"}), "3 to assign")

    def test_annotated_rows_are_shown_unless_hidden(self):
        self.client.force_login(self.user)
        url = reverse("reviews:review", args=[self.zipped.pk])
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        create_annotation(name, "Display name", self.user)
        shown = self.client.get(url)
        self.assertContains(shown, reverse("reviews:row", args=[self.zipped.pk, name.pk]))
        self.assertContains(shown, "status-dot--decided")
        self.assertContains(shown, 'name="hide"')
        self.assertNotContains(shown, "checked")
        hidden = self.client.get(url, {"hide": "1"}, HTTP_HX_REQUEST="true")
        self.assertNotContains(hidden, reverse("reviews:row", args=[self.zipped.pk, name.pk]))
        page = self.client.get(url, {"hide": "1"})
        self.assertContains(page, "checked")
        # the counts are the open rows either way
        self.assertContains(page, 'id="open-count" class="badge rounded-pill">3<')

    def test_the_filter_returns_the_groups_only(self):
        self.client.force_login(self.user)
        url = reverse("reviews:review", args=[self.zipped.pk])
        found = self.client.get(url, {"q": "comm"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(found, "reviews/_groups.html")
        self.assertTemplateNotUsed(found, "reviews/base.html")
        self.assertContains(found, "App[]")  # its field "comment" matches: kept with its list
        self.assertNotContains(found, "Profile")
        nothing = self.client.get(url, {"q": "zzz"}, HTTP_HX_REQUEST="true")
        self.assertContains(nothing, "Nothing matches")

    def test_use_suggestion_updates_the_row_and_the_counts(self):
        self.client.force_login(self.user)
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        suggestion = review(self.zipped).triage
        chosen = next(item for item in suggestion if item.location == name).choices[0]
        response = self.client.post(
            reverse("schemas:triage", args=[name.pk]),
            {"action": "link", "annotation": chosen.annotation.pk, "upload": self.zipped.pk},
        )
        self.assertEqual(response["HX-Trigger"], f"triaged-{name.pk}")
        row = self.client.get(reverse("reviews:row", args=[self.zipped.pk, name.pk]))
        self.assertContains(row, "review-row--decided")
        self.assertContains(row, "status-dot--decided")
        self.assertContains(row, "Display name")
        self.assertNotContains(row, "Moved?")
        # out of band: the group is done, one row less to assign, one more data point decided
        self.assertContains(row, 'hx-swap-oob="true"', count=4)  # group, root, tab, progress
        self.assertContains(row, "done")
        self.assertContains(row, 'id="open-count" class="badge rounded-pill" hx-swap-oob="true">3<')
        self.assertContains(row, "1 of 5 annotated")

    def test_the_panel_leads_with_the_suggestion(self):
        self.client.force_login(self.user)
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, name.pk]))
        self.assertContains(panel, "Likely moved from")
        self.assertContains(panel, "Use suggestion: Display name")
        self.assertContains(panel, "data-primary-action")
        self.assertContains(panel, f"?upload={self.zipped.pk}")  # the dialog knows the upload
        self.assertContains(panel, "Available after annotating")
        self.assertContains(panel, "<summary>More details</summary>", html=True)
        self.assertContains(panel, f'data-copy="{name.path}"')
        missing = self.client.get(reverse("reviews:location", args=[self.zipped.pk, self.name.pk]))
        self.assertContains(missing, "Not in this upload")
        self.assertContains(missing, "Display name")  # its annotation

    def test_a_list_and_its_item_are_one_row(self):
        self.client.force_login(self.user)
        app = Location.objects.get(path="/user_data_tiktok.json/Comment/Comments/App")
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, app.pk]))
        self.assertContains(panel, "App[]")
        item = Location.objects.get(path=app.path + "/[]")
        # "Add annotation" names the item first: it carries the meaning
        self.assertContains(panel, reverse("schemas:triage", args=[item.pk]))
        self.assertContains(panel, "<dt>Each item</dt>", html=True)
        self.assertContains(panel, "<dt>The list</dt>", html=True)
        self.client.post(
            reverse("schemas:triage", args=[item.pk]),
            {"action": "new", "name": "Comment", "upload": self.zipped.pk},
        )
        row = self.client.get(reverse("reviews:row", args=[self.zipped.pk, app.pk]))
        self.assertNotContains(row, "review-row--decided")  # the list is still open
        # then the list, in its own step, its name prefilled
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, app.pk]))
        self.assertContains(panel, "Add annotation for the list")
        self.assertContains(panel, reverse("schemas:triage", args=[app.pk]))
        dialog = self.client.get(
            reverse("schemas:triage", args=[app.pk]), {"upload": self.zipped.pk}
        )
        self.assertContains(dialog, 'value="List of Comment"')
        self.client.post(
            reverse("schemas:triage", args=[app.pk]),
            {"action": "new", "name": "List of Comment", "upload": self.zipped.pk},
        )
        row = self.client.get(reverse("reviews:row", args=[self.zipped.pk, app.pk]))
        self.assertContains(row, "review-row--decided")  # both decided
        self.assertContains(row, f"triaged-{item.pk} from:body")


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
        page = self.client.get(reverse("reviews:review", args=[later.pk]), {"tab": "changed"})
        self.assertContains(page, "<code>%Y-%m-%d</code>", html=True)
        self.assertContains(page, "format:")
        self.assertContains(page, "→")
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
        page = self.client.get(reverse("reviews:review", args=[broken.pk]), {"tab": "changed"})
        self.assertContains(page, "kind:")
        self.assertContains(page, "<code>unreadable file</code>", html=True)  # plain words
        self.assertNotContains(page, "(now )")
