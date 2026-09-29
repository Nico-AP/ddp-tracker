"""The review page: one row per data point with a status that explains itself, tabs, and a side
panel in the context of the reviewed upload.
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.reviews.services import KNOWN, NEW, review, scopes
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
        self.user = User.objects.create_user("curator", is_staff=True)  # staff decide directly
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

    def test_similar_paths_compared_and_annotated_together(self):
        """A moved path whose earlier path isn't annotated: the dialog compares the two, and one
        new annotation can be for both."""
        new_date = Location.objects.get(path="/user_data_tiktok.json/Comment/Comments/App/[]/date")
        old_date = Location.objects.get(path="/Comment/Comments/App/[]/date")
        self.client.force_login(self.user)
        # the panel says why there is no one-click suggestion
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, new_date.pk]))
        self.assertContains(panel, "compare them in the dialog")
        dialog_url = reverse("schemas:triage", args=[new_date.pk])
        dialog = self.client.get(dialog_url, {"upload": self.zipped.pk})
        self.assertContains(dialog, "Similar paths")
        self.assertContains(dialog, f"<code>{old_date.path}</code>", html=True)
        self.assertContains(dialog, '<th scope="row">Format</th>', html=True)
        self.assertContains(dialog, "%Y-%m-%d", count=2)  # both sides' format
        self.assertContains(
            dialog,
            f'<input type="checkbox" class="form-check-input" id="also-{old_date.pk}" name="also"'
            f' value="{old_date.pk}" form="new-annotation">',
            html=True,
        )
        # only paths the dialog offered: the annotated one isn't
        refused = self.client.post(
            dialog_url,
            {"action": "new", "name": "Date", "upload": self.zipped.pk, "also": [self.name.pk]},
        )
        self.assertEqual(refused.status_code, 400)
        self.client.post(
            dialog_url,
            {"action": "new", "name": "Date", "upload": self.zipped.pk, "also": [old_date.pk]},
        )
        new_date.refresh_from_db()
        old_date.refresh_from_db()
        self.assertIsNotNone(new_date.annotation)
        self.assertEqual(old_date.annotation, new_date.annotation)  # the same data point

    def test_an_annotated_similar_path_is_offered_as_is(self):
        new_name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        self.client.force_login(self.user)
        dialog = self.client.get(
            reverse("schemas:triage", args=[new_name.pk]), {"upload": self.zipped.pk}
        )
        self.assertContains(dialog, "Link to Display name")
        self.assertNotContains(dialog, 'name="also"')  # annotated already: nothing to join
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, new_name.pk]))
        self.assertNotContains(panel, "compare them in the dialog")

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
        # the list and its item are one row: App[], its fields date and comment, and name; all
        # new here (the earlier upload was a single file: every path moved), none known
        self.assertContains(page, 'New <span class="badge rounded-pill">4</span>')
        self.assertContains(page, 'Known <span class="badge rounded-pill">0</span>')
        self.assertContains(page, '<span id="open-count">4</span> to assign')
        self.assertContains(page, "Only missing annotations")
        known = self.client.get(url, {"tab": "known"})
        self.assertContains(known, "No known data points")
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
        self.assertContains(page, "data-annotating")  # Enter annotates here
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
        hidden = self.client.get(url, {"hide": "1"}, headers={"hx-request": "true"})
        self.assertNotContains(hidden, reverse("reviews:row", args=[self.zipped.pk, name.pk]))
        page = self.client.get(url, {"hide": "1"})
        self.assertContains(page, "checked")
        # the counts are the open rows either way
        self.assertContains(page, '<span id="open-count">3</span> to assign')

    def test_the_filter_returns_the_groups_only(self):
        self.client.force_login(self.user)
        url = reverse("reviews:review", args=[self.zipped.pk])
        found = self.client.get(url, {"q": "comm"}, headers={"hx-request": "true"})
        self.assertTemplateUsed(found, "schemas/tree/_groups.html")
        self.assertTemplateNotUsed(found, "reviews/base.html")
        self.assertContains(found, "App[]")  # its field "comment" matches: kept with its list
        self.assertNotContains(found, "Profile")
        nothing = self.client.get(url, {"q": "zzz"}, headers={"hx-request": "true"})
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
        row = self.client.get(
            reverse("reviews:row", args=[self.zipped.pk, name.pk]), {"tab": "new"}
        )
        self.assertContains(row, "review-row--decided")
        self.assertContains(row, "status-dot--decided")
        self.assertContains(row, "Display name")
        self.assertNotContains(row, "Moved?")
        # out of band: the group is done, one row less to assign, one more data point decided
        self.assertContains(row, 'hx-swap-oob="true"', count=4)  # group, root, tab, progress
        self.assertContains(row, "done")
        self.assertContains(row, '<span id="open-count" hx-swap-oob="true">3</span>', html=True)
        self.assertContains(row, "?tab=new")  # it reloads in its tab again
        self.assertContains(row, "1 of 5 annotated")

    def test_the_panel_leads_with_the_suggestion(self):
        self.client.force_login(self.user)
        name = Location.objects.get(path="/user_data_tiktok.json/Profile/name")
        panel = self.client.get(reverse("reviews:location", args=[self.zipped.pk, name.pk]))
        self.assertContains(panel, "Likely moved from")
        self.assertRegex(panel.content.decode(), r"Use suggestion:\s+Display name")
        self.assertContains(panel, "data-primary-action")
        self.assertContains(panel, f"?upload={self.zipped.pk}")  # the dialog knows the upload
        # examples before annotating too
        self.assertContains(panel, '<h3 class="review-panel__label">Example values</h3>', html=True)
        self.assertContains(panel, reverse("schemas:examples", args=[name.pk]))
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
            user=self.user,  # the review is its uploader's
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
            self.platform,
            {"a.json": b"{"},
            requested_at=date(2026, 1, 1),
            register=True,
            user=self.user,
        )
        diffs = {d.field: (d.before, d.now) for c in review(broken).changed for d in c.diffs}
        self.assertEqual(diffs["kind"], (("file",), "unmatched"))
        self.client.force_login(self.user)
        page = self.client.get(reverse("reviews:review", args=[broken.pk]), {"tab": "changed"})
        self.assertContains(page, "kind:")
        self.assertContains(page, "<code>unreadable file</code>", html=True)  # plain words
        self.assertNotContains(page, "(now )")


class TabTests(TestCase):
    """New, Known and Changed split the upload's data points; "Only to assign" narrows New and
    Known."""

    def setUp(self):
        self.user = User.objects.create_user("curator", is_staff=True)
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            self.platform,
            {"a.json": b'{"kept": "x", "typed": "2024-01-01"}'},
            requested_at=date(2026, 1, 1),
            register=True,
        )
        self.later = parsed_upload(
            self.platform,
            {"a.json": b'{"kept": "y", "typed": 5}', "b.json": b'{"added": 1}'},
            requested_at=date(2026, 6, 1),
            register=True,
        )
        self.url = reverse("reviews:review", args=[self.later.pk])
        self.client.force_login(self.user)

    def paths(self, tab):
        found = scopes(self.later)[tab]
        return set(Location.objects.filter(pk__in=found).values_list("path", flat=True))

    def test_each_data_point_is_in_one_tab(self):
        self.assertEqual(self.paths(NEW), {"/b.json/added"})
        self.assertEqual(self.paths(KNOWN), {"/a.json/kept"})
        changed = [item.observation.location.path for item in review(self.later).changed]
        self.assertEqual(changed, ["/a.json/typed"])  # its type is new: Changed only
        new = self.client.get(self.url)  # New is the first tab
        self.assertContains(new, "added")
        self.assertNotContains(new, "kept")
        known = self.client.get(self.url, {"tab": "known"})
        self.assertContains(known, "kept")
        self.assertNotContains(known, "added")
        self.assertContains(known, 'name="tab" value="known"')  # the filters stay in the tab

    def test_only_to_assign_in_known(self):
        kept = Location.objects.get(path="/a.json/kept")
        create_annotation(kept, "Kept", self.user)
        shown = self.client.get(self.url, {"tab": "known"})
        self.assertContains(shown, "status-dot--decided")
        self.assertContains(shown, '<span id="open-count">0</span> to assign')
        only = self.client.get(self.url, {"tab": "known", "hide": "1"})
        self.assertContains(only, "Everything here is annotated")
        # a row reloaded in Known counts what is left in Known
        row = self.client.get(
            reverse("reviews:row", args=[self.later.pk, kept.pk]), {"tab": "known"}
        )
        self.assertContains(row, '<span id="open-count" hx-swap-oob="true">0</span>', html=True)
        other = self.client.get(
            reverse("reviews:row", args=[self.later.pk, kept.pk]), {"tab": "new"}
        )
        self.assertContains(other, '<span id="open-count" hx-swap-oob="true">1</span>', html=True)

    def test_another_tabs_list_heads_its_new_fields_without_counting(self):
        platform = Platform.objects.create(name="YouTube", slug="youtube")
        parsed_upload(
            platform,
            {"v.json": b'{"Videos": [{"Date": "2024-01-01"}]}'},
            requested_at=date(2026, 1, 1),
            register=True,
        )
        later = parsed_upload(
            platform,
            {"v.json": b'{"Videos": [{"Date": "2024-01-01", "Likes": 3}]}'},
            requested_at=date(2026, 6, 1),
            register=True,
        )
        self.assertEqual(
            set(Location.objects.filter(pk__in=scopes(later)[NEW]).values_list("path", flat=True)),
            {"/v.json/Videos/[]/Likes"},
        )
        page = self.client.get(reverse("reviews:review", args=[later.pk]))
        # the known list heads its new field, dimmed, and isn't counted as to assign in New
        self.assertContains(page, "Videos[]")
        self.assertContains(page, "review-row--context", count=1)
        self.assertContains(page, 'New <span class="badge rounded-pill">1</span>')
        self.assertContains(page, '<span id="open-count">1</span> to assign')
