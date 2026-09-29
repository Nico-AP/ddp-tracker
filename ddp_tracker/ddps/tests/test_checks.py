"""Plausibility checks: the declared file format, similarity, and who may do what with a held
upload (ddps/checks.py).
"""

import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.checks import decide, similarity
from ddp_tracker.ddps.forms import UploadForm
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.tasks import parse_upload
from ddp_tracker.schemas.tests.test_workflow import ENGLISH, GERMAN
from ddp_tracker.users.models import User

Plausibility = Upload.Plausibility
UNRELATED = {"photos/list.json": b'{"albums": [{"cover": "x.jpg", "count": 3}]}'}


class FileFormatTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def form(self, name: str, data: bytes, file_format: str) -> UploadForm:
        return UploadForm(
            {
                "platform": self.platform.pk,
                "requested_at": "2026-01-01",
                "file_format": file_format,
            },
            {"file": SimpleUploadedFile(name, data)},
        )

    def test_accepts_what_it_was_told(self):
        cases = [
            ("export.zip", make_zip(ENGLISH), "zip"),
            ("posts.json", b'\xef\xbb\xbf  [{"a": 1}]', "json"),
            ("posts.csv", b"date;text\n2024-01-01;hi\n", "csv"),
        ]
        for name, data, file_format in cases:
            with self.subTest(name=name):
                form = self.form(name, data, file_format)
                self.assertTrue(form.is_valid(), form.errors)

    def test_refuses_something_else(self):
        cases = [
            ("export.json", make_zip(ENGLISH), "zip", "but this file isn&#x27;t a .zip"),
            ("export.zip", b"not a zip at all", "zip", "look like a ZIP archive"),
            ("posts.json", b"\x89PNG\r\n\x1a\n\x00", "json", "look like a JSON file"),
            ("posts.json", b"hello", "json", "look like a JSON file"),
            ("posts.csv", b"just one value\n", "csv", "look like a CSV file"),
        ]
        for name, data, file_format, message in cases:
            with self.subTest(name=name, data=data[:10]):
                form = self.form(name, data, file_format)
                self.assertFalse(form.is_valid())
                self.assertIn(message, str(form.errors["file"]))

    def test_the_format_is_required(self):
        form = self.form("export.zip", make_zip(ENGLISH), "")
        self.assertIn("file_format", form.errors)

    def test_parsed_format_must_match_the_declared_one(self):
        upload = Upload.objects.create(
            platform=self.platform, requested_at="2026-01-01", file_name="a.zip", file_format="csv"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a"
            path.write_bytes(make_zip(ENGLISH))
            parse_upload.call(upload.pk, str(path))
        upload.refresh_from_db()
        self.assertEqual(upload.status, Upload.Status.FAILED)
        self.assertEqual(upload.error, "Declared as a CSV file, but the file is ZIP.")
        self.assertIsNone(upload.registered_at)


class DecideTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def upload(self, members, **fields):
        upload = parsed_upload(self.platform, members, **fields)
        decide(upload)
        upload.refresh_from_db()
        return upload

    def test_the_first_of_its_kind_waits_for_approval(self):
        first = self.upload(ENGLISH)
        self.assertEqual(
            (first.plausibility, first.plausibility_reason, first.similarity),
            (Plausibility.AWAITING, Upload.Reason.FIRST, None),
        )
        self.assertIsNone(first.registered_at)
        self.assertFalse(first.counts)

    def test_similar_uploads_count_right_away(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        # moved and translated: still recognised through the suggestions
        german = self.upload(GERMAN, requested_at=date(2026, 6, 1))
        self.assertEqual(german.plausibility, Plausibility.PASSED)
        self.assertIsNotNone(german.registered_at)
        self.assertTrue(german.counts)
        self.assertGreaterEqual(german.similarity, 0.5)

    def test_unlike_uploads_need_the_uploaders_confirmation(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        odd = self.upload(UNRELATED)
        self.assertEqual(
            (odd.plausibility, odd.plausibility_reason),
            (Plausibility.UNCONFIRMED, Upload.Reason.DISSIMILAR),
        )
        self.assertEqual(odd.similarity, 0.0)
        self.assertIsNone(odd.registered_at)

    def test_nothing_to_recognise_is_unusual_too(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        odd = self.upload({"photos/p.bin": b"x"})  # an unreadable file only: no data points
        self.assertEqual((odd.plausibility, odd.similarity), (Plausibility.UNCONFIRMED, None))

    @override_settings(DDP_SIMILARITY_THRESHOLD=0.0)
    def test_the_threshold_is_a_setting(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        self.assertEqual(self.upload(UNRELATED).plausibility, Plausibility.PASSED)

    def test_exact_duplicates_dont_count_twice(self):
        first = parsed_upload(self.platform, ENGLISH, register=True)
        again = self.upload(ENGLISH)
        self.assertEqual(again.plausibility, Plausibility.DUPLICATE)
        self.assertIsNone(again.registered_at)
        self.assertEqual(list(again.duplicates()), [first])

    def test_peers_are_the_same_platform_and_format(self):
        other = Platform.objects.create(name="YouTube", slug="youtube")
        parsed_upload(other, ENGLISH, register=True)  # another platform: no peer
        self.assertEqual(self.upload(ENGLISH).plausibility, Plausibility.AWAITING)

    def test_similarity(self):
        english = parsed_upload(self.platform, ENGLISH)
        self.assertIsNone(similarity(english))  # nothing to compare with
        parsed_upload(self.platform, ENGLISH, register=True)
        self.assertEqual(similarity(english), 1.0)
        self.assertEqual(similarity(parsed_upload(self.platform, UNRELATED)), 0.0)


class HeldUploadTests(TestCase):
    """The uploader confirms or discards an unusual upload; staff approve or reject."""

    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.uploader = User.objects.create_user("uploader")
        self.other = User.objects.create_user("other")
        self.staff = User.objects.create_user("admin", is_staff=True)
        parsed_upload(self.platform, ENGLISH, register=True)
        self.odd = parsed_upload(self.platform, UNRELATED, user=self.uploader)
        decide(self.odd)

    def act(self, user, action, upload=None):
        self.client.force_login(user)
        upload = upload or self.odd
        return self.client.post(reverse("ddps:upload-decide", args=[upload.pk, action]))

    def state(self):
        self.odd.refresh_from_db()
        return self.odd.plausibility

    def test_the_uploader_is_asked(self):
        self.client.force_login(self.uploader)
        page = self.client.get(self.odd.get_absolute_url())
        self.assertContains(page, "doesn't look like the other TikTok ZIP uploads")
        self.assertContains(page, "only 0 % of its data points are known")
        self.assertContains(page, "Yes, ask for approval")
        self.assertContains(self.client.get(reverse("ddps:uploads")), "badge--unconfirmed")
        self.client.force_login(self.other)  # not theirs: as if it didn't exist
        self.assertEqual(self.client.get(self.odd.get_absolute_url()).status_code, 404)

    def test_confirm_then_approve(self):
        self.assertEqual(self.act(self.other, "confirm").status_code, 404)  # not theirs
        self.assertRedirects(self.act(self.uploader, "confirm"), self.odd.get_absolute_url())
        self.assertEqual(self.state(), Plausibility.AWAITING)
        self.assertEqual(self.act(self.other, "approve").status_code, 404)  # not staff
        self.client.force_login(self.staff)
        page = self.client.get(self.odd.get_absolute_url())
        self.assertContains(page, "Waiting for an admin")
        self.assertContains(page, ">Approve<")
        self.act(self.staff, "approve")
        self.odd.refresh_from_db()
        self.assertEqual(
            (self.odd.plausibility, self.odd.approved_by), (Plausibility.APPROVED, self.staff)
        )
        self.assertIsNotNone(self.odd.registered_at)
        self.assertEqual(self.act(self.staff, "approve").status_code, 403)  # decided already

    def test_reject(self):
        self.act(self.uploader, "confirm")
        self.act(self.staff, "reject")
        self.assertEqual(self.state(), Plausibility.REJECTED)
        self.assertIsNone(self.odd.registered_at)
        self.client.force_login(self.uploader)
        rejected = self.client.get(self.odd.get_absolute_url())
        self.assertContains(rejected, f"Rejected by #{self.staff.pk}")  # not by email
        self.assertNotContains(rejected, f"Rejected by {self.staff.email}")

    def test_discard(self):
        self.assertEqual(self.act(self.other, "discard").status_code, 404)
        self.assertRedirects(self.act(self.uploader, "discard"), reverse("ddps:uploads"))
        self.assertFalse(Upload.objects.filter(pk=self.odd.pk).exists())

    def test_staff_may_approve_their_own_uploads(self):
        own = parsed_upload(self.platform, UNRELATED, user=self.staff)
        decide(own)
        self.act(self.staff, "confirm", own)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(own.get_absolute_url()), ">Approve<")
        self.assertRedirects(self.act(self.staff, "approve", own), own.get_absolute_url())
        own.refresh_from_db()
        self.assertEqual(own.plausibility, Plausibility.APPROVED)

    def test_approvals_page_and_navigation(self):
        self.act(self.uploader, "confirm")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("ddps:approvals")).status_code, 302)
        self.assertNotContains(self.client.get(reverse("ddps:uploads")), "Approvals (")
        self.client.force_login(self.staff)
        page = self.client.get(reverse("ddps:approvals"))
        self.assertContains(page, self.odd.get_absolute_url())
        self.assertContains(page, "Unlike the other uploads of its platform and format")
        self.assertContains(self.client.get(reverse("ddps:uploads")), "Approvals (1)")
        self.act(self.staff, "approve")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("ddps:approvals")), "Nothing is waiting")

    def test_unknown_actions_are_refused(self):
        self.client.force_login(self.uploader)
        url = f"/uploads/{self.odd.pk}/delete/"
        self.assertEqual(self.client.post(url).status_code, 404)


class TaskTests(TestCase):
    def test_a_failing_check_fails_the_upload_as_a_whole(self):
        platform = Platform.objects.create(name="TikTok", slug="tiktok")
        upload = Upload.objects.create(
            platform=platform, requested_at="2026-01-01", file_name="a.zip", file_format="zip"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a"
            path.write_bytes(make_zip(ENGLISH))
            with (
                mock.patch("ddp_tracker.ddps.tasks.decide", side_effect=RuntimeError("boom")),
                self.assertRaises(RuntimeError),
                self.assertLogs("ddp_tracker.ddps.tasks", "ERROR"),
            ):
                parse_upload.call(upload.pk, str(path))
            self.assertFalse(path.exists())
        upload.refresh_from_db()
        # not left parsed-but-unchecked: the document isn't kept, the upload failed
        self.assertEqual(upload.status, Upload.Status.FAILED)
        self.assertIsNone(upload.document)
        self.assertEqual(upload.plausibility, Plausibility.PENDING)
