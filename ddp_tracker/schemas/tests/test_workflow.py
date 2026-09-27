from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from ddp_parser import from_dict
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.reviews.services import review
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.services import (
    create_annotation,
    flatten,
    link,
    register_upload,
    type_label,
)
from ddp_tracker.users.models import User

ENGLISH = {
    "activity/watch_history.json": b'[{"Date": "2024-01-01 10:00:00", "Link": "https://x.y/1"}]',
    "profile/profile.json": b'{"name": "Anna", "email": "a@b.ch", "joined": "2024-01-01"}',
}

GERMAN = {
    "your_activity/activity/watch_history.json": b'[{"Datum": "2024-02-02 11:00:00", "Link": "https://x.y/2"}]',
    "profile/profile.json": b'{"name": "Ben", "joined": "02.01.2024"}',
}


class ScenarioTests(TestCase):
    """The workflow: register, create annotations, recognise them in a moved, translated export."""

    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.english = parsed_upload(
            self.platform, ENGLISH, language="en", requested_at=date(2026, 1, 1), register=True
        )

    def test_first_upload_is_all_new(self):
        result = review(self.english)
        paths = [item.location.path for item in result.triage]
        self.assertEqual(
            paths,
            [
                "/activity/watch_history.json",  # the file is a list
                "/activity/watch_history.json/[]",  # its item: one watched video
                "/activity/watch_history.json/[]/Date",
                "/activity/watch_history.json/[]/Link",
                "/profile/profile.json/name",
                "/profile/profile.json/email",
                "/profile/profile.json/joined",
            ],
        )
        self.assertTrue(all(item.is_new and not item.choices for item in result.triage))
        self.assertEqual((result.changed, result.missing), ([], []))

    def test_annotations_survive_moves_and_languages(self):
        # a curator annotates every data point of the first export, one by one
        for item in review(self.english).triage:
            create_annotation(item.location, item.location.default_name, self.user)
        self.assertEqual(Annotation.objects.count(), 7)
        date_annotation = Annotation.objects.get(name="Date")
        german = parsed_upload(
            self.platform, GERMAN, language="de", requested_at=date(2026, 6, 1), register=True
        )
        result = review(german)
        choices = {
            item.location.path: [(c.annotation.name, c.reason) for c in item.choices]
            for item in result.triage
        }
        self.assertEqual(
            choices,
            {
                "/your_activity/activity/watch_history.json": [("watch_history", "moved")],
                "/your_activity/activity/watch_history.json/[]": [("watch_history item", "moved")],
                "/your_activity/activity/watch_history.json/[]/Datum": [("Date", "renamed")],
                "/your_activity/activity/watch_history.json/[]/Link": [("Link", "moved")],
            },
        )
        # the curator follows each suggestion, one by one
        for item in review(german).triage:
            link(item.location, item.choices[0].annotation)
        self.assertEqual(
            sorted(date_annotation.locations.values_list("path", flat=True)),
            [
                "/activity/watch_history.json/[]/Date",
                "/your_activity/activity/watch_history.json/[]/Datum",
            ],
        )
        self.assertEqual(review(german).triage, [])
        # "joined" is written differently now; email wasn't in this export
        self.assertEqual(
            [(c.observation.location.path, c.fields) for c in result.changed],
            [("/profile/profile.json/joined", ["format"])],
        )
        self.assertEqual(
            [m.location.path for m in review(german).missing], ["/profile/profile.json/email"]
        )
        # the annotation page shows both locations and their languages
        response = self.client.get(date_annotation.get_absolute_url())
        self.assertContains(response, "/your_activity/activity/watch_history.json/[]/Datum")
        self.assertContains(response, "<td>de</td>", html=True)
        self.assertContains(response, "<td>en</td>", html=True)

    def test_profiles_follow_request_dates_not_registration_order(self):
        parsed_upload(self.platform, GERMAN, requested_at=date(2025, 1, 1), register=True)  # older
        joined = Location.objects.get(path="/profile/profile.json/joined")
        profile = profiles([joined.pk], Observation.objects.all())[joined.pk]
        self.assertEqual(
            (profile.first_seen, profile.last_seen, profile.uploads),
            (date(2025, 1, 1), date(2026, 1, 1), 2),
        )
        self.assertEqual(profile.formats, {"%Y-%m-%d": 1, "%d.%m.%Y": 1})
        self.assertEqual(profile.variants, 1)

    def test_registering_twice_does_nothing(self):
        register_upload(self.english)
        self.assertEqual(Observation.objects.filter(location__path="").count(), 1)
        self.assertEqual(self.english.root_format, "zip")

    def test_unique_annotation_names(self):
        location = Location.objects.get(path="/profile/profile.json/name")
        other = Location.objects.get(path="/profile/profile.json/email")
        self.assertEqual(create_annotation(location, "name", None).name, "name")
        self.assertEqual(create_annotation(other, "name", None).name, "name (2)")

    def test_helpers(self):
        location = Location.objects.get(path="/activity/watch_history.json/[]/Date")
        self.assertEqual(location.default_name, "Date")
        # a file that is a list is named without its extension
        history = Location.objects.get(path="/activity/watch_history.json")
        self.assertEqual(history.default_name, "watch_history")
        item = Location.objects.get(path="/activity/watch_history.json/[]")
        self.assertEqual(item.default_name, "watch_history item")
        self.assertEqual(item.display_name, "<item>")
        self.assertEqual(
            str(Observation.objects.filter(location=location).get()),
            f"TikTok: {location.path} in upload {self.english.pk}",
        )
        assert self.english.document is not None
        root = from_dict(self.english.document).root
        self.assertEqual(next(flatten(root)).parent_path, None)
        self.assertEqual(type_label(root), "")


DATUM = "/your_activity/activity/watch_history.json/[]/Datum"


class SuggestionReferenceTests(TestCase):
    """Suggestions are computed against the uploads requested strictly earlier, whatever the
    order in which they were registered.
    """

    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def suggested(self, upload):
        observation = upload.observations.get(location__path=DATUM)
        return [c["path"] for c in observation.suggestions]

    def test_an_older_export_registered_later_updates_newer_suggestions(self):
        german = parsed_upload(self.platform, GERMAN, requested_at=date(2026, 6, 1), register=True)
        self.assertEqual(self.suggested(german), [])
        parsed_upload(self.platform, ENGLISH, requested_at=date(2026, 1, 1), register=True)
        self.assertEqual(self.suggested(german), ["/activity/watch_history.json/[]/Date"])

    def test_same_date_and_later_uploads_are_no_reference(self):
        german = parsed_upload(self.platform, GERMAN, requested_at=date(2026, 6, 1), register=True)
        parsed_upload(self.platform, ENGLISH, requested_at=date(2026, 6, 1), register=True)
        parsed_upload(self.platform, ENGLISH, requested_at=date(2026, 9, 1), register=True)
        self.assertEqual(self.suggested(german), [])


class RefreshObservationsTests(TestCase):
    def test_reapplies_the_data_point_rule(self):
        platform = Platform.objects.create(name="X", slug="x")
        parsed_upload(platform, {"a.json": b'{"o": {"k": 1}}'}, register=True)
        Observation.objects.update(is_data_point=True)  # as if registered under an older rule
        out = StringIO()
        call_command("refresh_observations", stdout=out)
        flags = dict(Observation.objects.values_list("location__path", "is_data_point"))
        self.assertEqual(
            flags, {"": False, "/a.json": False, "/a.json/o": False, "/a.json/o/k": True}
        )
        self.assertIn("Updated 3 observations.", out.getvalue())

    def test_recomputes_suggestions(self):
        platform = Platform.objects.create(name="X", slug="x")
        parsed_upload(platform, ENGLISH, requested_at=date(2026, 1, 1), register=True)
        german = parsed_upload(platform, GERMAN, requested_at=date(2026, 6, 1), register=True)
        expected = dict(german.observations.values_list("pk", "suggestions"))
        self.assertTrue(any(expected.values()))
        Observation.objects.update(suggestions=[])  # as if suggested under an older rule
        call_command("refresh_observations", stdout=StringIO())
        self.assertEqual(dict(german.observations.values_list("pk", "suggestions")), expected)


class ViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.upload = parsed_upload(self.platform, ENGLISH, register=True)
        self.name = Location.objects.get(path="/profile/profile.json/name")

    def keys(self, response):
        return [row.key for group in response.context["tree"].groups for row in group.lines()]

    def test_platform_explorer_is_public(self):
        response = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(response, "7 not yet assigned")
        self.assertContains(response, "data-review-tree")  # the review's tree
        self.assertNotContains(response, "Recent uploads")
        self.assertIn("/profile/profile.json/name", self.keys(response))
        detail = self.client.get(
            reverse("schemas:location", args=["tiktok"]), {"path": self.name.path}
        )
        self.assertContains(detail, "Not assigned to an annotation yet")
        self.assertNotContains(detail, "Add annotation")

    def test_root_is_the_format_not_the_file(self):
        response = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(response, '<a class="nav-link active"', count=1)  # ZIP archive
        self.assertContains(response, "ZIP archive")
        root = Location.objects.get(platform=self.platform, path="")
        self.assertIsNone(root.name)  # the uploaded file's name is not kept
        self.assertNotContains(response, "export.zip")
        detail = self.client.get(reverse("schemas:location", args=["tiktok"]), {"path": ""})
        self.assertContains(detail, "Root")
        self.assertNotContains(detail, "export.zip")

    def test_one_format_per_tree(self):
        csv_only = Platform.objects.create(name="Spotify", slug="spotify")
        parsed_file(csv_only, "streams.csv", b"track,ms\nA,1000\n", register=True)
        url = reverse("schemas:platform", args=["spotify"])
        response = self.client.get(url)
        self.assertEqual(response.context["filter"].root_format, "csv")
        (root,) = response.context["tree"].roots
        self.assertEqual(root.title, [("CSV file", True)])  # a single file's tree
        parsed_upload(csv_only, {"streams.csv": b"track,ms\nB,2000\n"}, register=True)
        parsed_upload(csv_only, {"streams.csv": b"track,ms\nC,3000\n"}, register=True)
        response = self.client.get(url)  # the most common format now
        self.assertEqual(response.context["filter"].root_format, "zip")
        self.assertTrue(all(key.startswith("/streams.csv") for key in self.keys(response)))
        self.assertContains(response, "?root_format=csv")  # the other one, one click away
        csv = self.client.get(url, {"root_format": "csv"})
        self.assertFalse(any(key.startswith("/streams.csv") for key in self.keys(csv)))

    def test_rows_are_alphabetical(self):
        parsed_upload(self.platform, {"a_first.json": b'{"z": 1, "a": 2}'}, register=True)
        response = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        keys = self.keys(response)
        self.assertLess(keys.index("/a_first.json/a"), keys.index("/a_first.json/z"))

    def test_edit_examples(self):
        url = reverse("schemas:examples", args=[self.name.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "Example values")
        response = self.client.post(url, {"example_values": "Jane Doe\n\n  Max Muster "})
        self.assertContains(response, "<code>Jane Doe</code>", html=True)
        self.assertContains(response, "user input")
        self.name.refresh_from_db()
        self.assertEqual(
            self.name.example_values,
            [
                {"value": "Jane Doe", "source": "user_input"},
                {"value": "Max Muster", "source": "user_input"},
            ],
        )
        self.assertContains(self.client.get(url), "Jane Doe\nMax Muster")
        detail = self.client.get(
            reverse("schemas:location", args=["tiktok"]), {"path": self.name.path}
        )
        self.assertContains(detail, "Edit examples")

    def test_only_data_nodes_and_media_are_annotatable(self):
        self.client.force_login(self.user)
        detail = reverse("schemas:location", args=["tiktok"])
        # a list, its item, a value
        for path in [
            "/activity/watch_history.json",
            "/activity/watch_history.json/[]",
            "/profile/profile.json/name",
        ]:
            with self.subTest(path=path):
                self.assertContains(self.client.get(detail, {"path": path}), "Add annotation")
        parsed_upload(
            self.platform, {"photos/p.png": b"\x89PNG\r\n\x1a\n" + b"\0" * 32}, register=True
        )
        self.assertContains(self.client.get(detail, {"path": "/photos/p.png"}), "Add annotation")
        for path in ["", "/profile", "/profile/profile.json"]:  # root, folder, object file
            with self.subTest(path=path):
                self.assertNotContains(self.client.get(detail, {"path": path}), "Add annotation")

    def test_review_requires_login(self):
        url = reverse("reviews:review", args=[self.upload.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "To assign")

    def test_unregistered_upload_review(self):
        self.client.force_login(self.user)
        other = parsed_upload(self.platform, ENGLISH)
        self.assertContains(
            self.client.get(reverse("reviews:review", args=[other.pk])),
            "isn't part of the collected schema",
        )

    def test_triage_actions(self):
        url = reverse("schemas:triage", args=[self.name.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  # the modal needs a login
        self.client.force_login(self.user)
        modal = self.client.get(url, {"upload": self.upload.pk})
        self.assertContains(modal, "New annotation")
        self.assertContains(modal, 'value="name"')  # the default name
        for field in ("name", "description", "note"):
            self.assertContains(modal, f'name="{field}"')
        response = self.client.post(
            url,
            {
                "action": "new",
                "name": "Display name",
                "description": " The account's shown name. ",
                "note": "Set at sign-up",
                "upload": self.upload.pk,
            },
        )
        created = Annotation.objects.get(name="Display name")
        self.assertEqual(
            (created.description, created.note), ("The account's shown name.", "Set at sign-up")
        )
        # nothing to show: the modal closes, and the row reloads on the event
        self.assertEqual(response.content, b"")
        self.assertEqual(response["HX-Trigger"], f"triaged-{self.name.pk}")
        row = self.client.get(reverse("reviews:row", args=[self.upload.pk, self.name.pk]))
        self.assertContains(row, "Display name")
        self.assertContains(row, "status-dot--decided")
        annotation = Annotation.objects.get(name="Display name")
        other = Location.objects.get(path="/profile/profile.json/email")
        other_url = reverse("schemas:triage", args=[other.pk])
        self.client.post(other_url, {"action": "link", "annotation": annotation.pk, "upload": ""})
        self.assertEqual(Location.objects.get(pk=other.pk).annotation, annotation)
        self.assertContains(self.client.get(other_url), "Remove assignment")
        self.client.post(other_url, {"action": "ignore"})
        self.assertTrue(Location.objects.get(pk=other.pk).ignored)
        self.client.post(other_url, {"action": "reset", "upload": self.upload.pk})
        self.assertFalse(Location.objects.get(pk=other.pk).ignored)
        panel_url = reverse("schemas:location", args=["tiktok"])
        panel = self.client.get(panel_url, {"path": other.path})
        self.assertContains(panel, "Add annotation")
        # the panel swaps itself (outerHTML); the button must not inherit that and replace the modal
        self.assertRegex(panel.content.decode(), r'hx-target="#modal"\s+hx-swap="innerHTML"')
        self.client.logout()
        self.assertNotContains(self.client.get(panel_url, {"path": other.path}), "Add annotation")

    def test_existing_annotations_are_a_searchable_table(self):
        self.client.force_login(self.user)
        first = create_annotation(self.name, "Display name", self.user, description="Shown")
        email = Location.objects.get(path="/profile/profile.json/email")
        create_annotation(email, "Email", self.user)
        modal = self.client.get(
            reverse("schemas:triage", args=[email.pk]), {"upload": self.upload.pk}
        )
        self.assertContains(modal, 'data-filter-table="#existing-annotations"')
        self.assertContains(modal, 'data-filter-text="display name shown"')
        self.assertContains(modal, f'name="annotation" value="{first.pk}"')  # one Link form each
        self.assertContains(modal, ">Link</button>", count=2)
        self.assertContains(modal, "No annotation matches.")

    def test_no_bulk_actions(self):
        # every data point is decided on its own: nothing on the page acts on several at once
        self.client.force_login(self.user)
        page = self.client.get(reverse("reviews:review", args=[self.upload.pk]))
        for text in ("Accept all", "everything left", "New annotations for all"):
            self.assertNotContains(page, text)
        self.assertContains(page, "data-panel-open")  # one data point at a time, in the panel
