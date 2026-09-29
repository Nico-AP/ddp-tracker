"""The platform explorer's tree (schemas/explorer.py) and page: the review's design over all
uploads of one root format, muted rows for nodes that are never data points, an informative
side panel."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.representations.models import ObjectType, Pattern, Representation
from ddp_tracker.schemas.examples import USER_INPUT, add_examples
from ddp_tracker.schemas.explorer import (
    MISSING_ANNOTATIONS,
    MISSING_REPRESENTATIONS,
    explorer_tree,
)
from ddp_tracker.schemas.filters import SchemaFilter
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.users.models import User

EARLY = {"a.json": b'{"when": "2024-01-01", "tags": ["x"]}'}
LATE = {
    "a.json": b'{"when": "01.02.2024", "tags": ["x"], "meta": {}}',
    "notes.txt": b"free text",
}


class ExplorerTreeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(self.platform, EARLY, requested_at=date(2025, 1, 1), register=True)
        parsed_upload(self.platform, LATE, requested_at=date(2026, 1, 1), register=True)
        self.filter = SchemaFilter(request_format="json")

    def rows(self, **kwargs):
        tree = explorer_tree(self.platform, self.filter, **kwargs)
        return {row.key: row for group in tree.groups for row in group.lines()}

    def test_rows_over_all_uploads_the_latest_as_representative(self):
        rows = self.rows()
        self.assertEqual(rows["/a.json/when"].observation.format, "%d.%m.%Y")  # the 2026 one
        self.assertEqual(rows["/a.json/when"].summary, "%d.%m.%Y")
        tags = rows["/a.json/tags"]
        self.assertEqual((tags.name, tags.summary), ("tags[]", "1 item"))

    def test_examples_are_the_preview(self):
        when = Location.objects.get(path="/a.json/when")
        add_examples(when, ["2024-01-01", "01.02.2024"], USER_INPUT)
        row = self.rows()["/a.json/when"]
        self.assertEqual((row.preview, row.more), (["2024-01-01"], 1))

    def test_muted_rows_for_what_is_never_a_data_point(self):
        rows = self.rows()
        self.assertTrue(rows["/a.json/meta"].muted)  # an object always seen empty
        self.assertTrue(rows["/notes.txt"].muted)  # not read
        self.assertFalse(rows["/a.json/when"].muted)
        page = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(page, "review-row--muted", count=2)
        self.assertContains(page, "always empty")
        self.assertContains(page, "not read")
        # never counted
        tree = explorer_tree(self.platform, self.filter)
        self.assertEqual(tree.open_count, 2)  # when, tags[] (list and item: one row); no muted

    def test_show_missing_annotations_or_representations(self):
        create_annotation(Location.objects.get(path="/a.json/when"), "When", self.user)
        create_annotation(Location.objects.get(path="/a.json/tags/[]"), "Tag", self.user)
        create_annotation(Location.objects.get(path="/a.json/tags"), "List of Tag", self.user)
        self.assertIn("/a.json/when", self.rows())  # all, muted rows too
        self.assertIn("/a.json/meta", self.rows())
        # nothing is left without an annotation (muted rows never count)
        self.assertEqual(self.rows(show=MISSING_ANNOTATIONS), {})
        # no list of objects: nothing to represent
        self.assertEqual(self.rows(show=MISSING_REPRESENTATIONS), {})
        parsed_upload(
            self.platform,
            {"b.json": b'{"videos": [{"id": 1}]}'},
            requested_at=date(2026, 2, 1),
            register=True,
        )
        # a list of objects, not annotated: no matter; once represented, gone
        self.assertEqual(set(self.rows(show=MISSING_REPRESENTATIONS)), {"/b.json/videos"})
        Representation.objects.create(
            location=Location.objects.get(path="/b.json/videos/[]"),
            pattern=Pattern.OBJECT,
            name="Video",
            object=ObjectType.objects.get(slug="video"),
        )
        self.assertEqual(self.rows(show=MISSING_REPRESENTATIONS), {})

    def test_the_filter(self):
        self.assertEqual(set(self.rows(q="TAG")), {"/a.json/tags"})


class ExplorerPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(self.platform, LATE, register=True)
        self.tags = Location.objects.get(path="/a.json/tags")
        self.item = Location.objects.get(path="/a.json/tags/[]")

    def test_the_panel_is_informative(self):
        self.client.force_login(self.user)
        panel = self.client.get(
            reverse("schemas:location", args=["tiktok"]), {"path": self.tags.path}
        )
        for heading in ("Annotation", "Example values", "Representations", "Data structure"):
            self.assertContains(panel, f'<h3 class="review-panel__label">{heading}</h3>', html=True)
        # a list's row: the item first (the meaning), then the list; Enter doesn't annotate here
        self.assertContains(panel, '<p class="review-panel__entry">Each item</p>', html=True)
        self.assertContains(panel, '<p class="review-panel__entry">The list</p>', html=True)
        self.assertNotContains(panel, "data-primary-action")
        self.assertContains(panel, f"triaged-{self.item.pk} from:body")
        create_annotation(self.item, "Tag", self.user)
        panel = self.client.get(
            reverse("schemas:location", args=["tiktok"]), {"path": self.tags.path}
        )
        self.assertContains(panel, "Not annotated yet")  # the list is still open
        self.assertContains(panel, f"{reverse('schemas:triage', args=[self.tags.pk])}")

    def test_the_row_reloads_after_a_change(self):
        url = reverse("schemas:row", args=["tiktok", self.tags.pk])
        self.assertNotContains(self.client.get(url), "review-pill--done")
        create_annotation(self.item, "Tag", self.user)
        create_annotation(self.tags, "List of Tag", self.user)
        row = self.client.get(url, {"request_format": "json"})
        self.assertContains(
            row, '<span class="review-pill review-pill--done">Tag</span>', html=True
        )
        self.assertNotContains(row, "status-dot")  # no assignment state in the explorer
        self.assertNotContains(row, "hx-swap-oob")

    def test_no_assignment_information_in_the_explorer(self):
        page = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        for absent in ("status-dot", "to assign", "data-annotating", "<kbd>Enter</kbd>"):
            with self.subTest(absent=absent):
                self.assertNotContains(page, absent)

    def test_the_show_selector(self):
        url = reverse("schemas:platform", args=["tiktok"])
        page = self.client.get(url)
        for label in ("Show all", "Show missing annotations", "Show missing representations"):
            self.assertContains(page, label)
        self.assertRegex(page.content.decode(), r'id="show-all"\s+value="all"\s+checked')
        self.assertNotContains(page, "Hide annotated")
        create_annotation(self.item, "Tag", self.user)
        create_annotation(self.tags, "List of Tag", self.user)
        groups = self.client.get(url, {"show": "representations"}, headers={"hx-request": "true"})
        self.assertNotContains(groups, "tags[]")  # a list of values: nothing to represent
        self.assertContains(groups, "Every list of objects here has a representation.")
        done = self.client.get(
            url, {"show": "annotations", "q": "tags"}, headers={"hx-request": "true"}
        )
        self.assertContains(done, "Nothing matches")
        odd = self.client.get(url, {"show": "nonsense"})
        self.assertEqual(odd.context["show"], "all")


class OrderTests(TestCase):
    """The explorer is alphabetical, ignoring case: positions in a file differ between uploads."""

    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def keys(self):
        tree = explorer_tree(self.platform, SchemaFilter(request_format="json"))
        return [row.key for group in tree.groups for row in group.lines()]

    def groups(self):
        tree = explorer_tree(self.platform, SchemaFilter(request_format="json"))
        return [(root.path, group.path) for root in tree.roots for group in root.groups]

    def test_keys_from_different_uploads(self):
        parsed_upload(self.platform, {"a.json": b'{"b": 1, "a": 1}'}, register=True)
        parsed_upload(
            self.platform,
            {"a.json": b'{"c": 1, "a": 1}'},
            requested_at=date(2026, 12, 1),
            register=True,
        )
        self.assertEqual(self.keys(), ["/a.json/a", "/a.json/b", "/a.json/c"])

    def test_ignoring_case_with_variants_side_by_side(self):
        parsed_upload(
            self.platform,
            {"a.json": b'{"Zeta": 1, "alpha": 1, "TikTok Live": {"x": 1}}'},
            register=True,
        )
        parsed_upload(
            self.platform,
            {"a.json": b'{"Tiktok Live": {"x": 1}, "beta": {"y": 1}}'},
            requested_at=date(2026, 12, 1),
            register=True,
        )
        self.assertEqual(
            [group for _, group in self.groups()],
            ["/a.json", "/a.json/beta", "/a.json/TikTok Live", "/a.json/Tiktok Live"],
        )
        loose = self.keys()[:2]
        self.assertEqual(loose, ["/a.json/alpha", "/a.json/Zeta"])

    def test_files_alphabetical_list_fields_below_their_list(self):
        parsed_upload(
            self.platform,
            {"b.json": b'{"k": 1}', "a.json": b'{"L": [{"z": 1, "a": 2}], "m": 1}'},
            register=True,
        )
        self.assertEqual([root for root, _ in self.groups()], ["/a.json", "/b.json"])
        self.assertEqual(
            self.keys(),
            ["/a.json/L", "/a.json/L/[]/a", "/a.json/L/[]/z", "/a.json/m", "/b.json/k"],
        )
