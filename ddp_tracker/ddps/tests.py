import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.tasks import parse_upload
from ddp_tracker.schemas.models import Location
from ddp_tracker.users.models import User

PROFILE = {"profile.json": b'{"name": "Fritzli", "joined": "2024-01-01"}'}


class UploadFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="Instagram", slug="instagram")
        self.incoming = tempfile.TemporaryDirectory()
        self.addCleanup(self.incoming.cleanup)
        settings = override_settings(DDP_INCOMING_DIR=self.incoming.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def post(self, data: bytes, name: str = "export.zip"):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("ddps:upload-create"),
                {
                    "platform": self.platform.pk,
                    "requested_at": "2026-09-01",
                    "language": "de",
                    "file": SimpleUploadedFile(name, data),
                },
            )

    def test_login_required(self):
        response = self.client.get(reverse("ddps:upload-create"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('ddps:upload-create')}")

    def test_upload_is_parsed_and_the_file_deleted(self):
        response = self.post(make_zip(PROFILE))
        upload = Upload.objects.get()
        self.assertRedirects(response, upload.get_absolute_url())
        self.assertEqual(upload.status, Upload.Status.DONE)
        self.assertEqual(
            (upload.language, upload.uploaded_by, upload.file_name), ("de", self.user, "export.zip")
        )
        assert upload.document is not None
        self.assertEqual(upload.document["root"]["children"][0]["path"], "/profile.json")
        self.assertEqual(len(upload.source_sha256), 64)
        self.assertEqual(list(Path(self.incoming.name).iterdir()), [])  # nothing kept
        self.assertIsNotNone(upload.registered_at)  # added to the collected schema
        self.assertTrue(Location.objects.filter(path="/profile.json/joined").exists())

    def test_unreadable_zip_fails_and_is_deleted(self):
        broken = make_zip(PROFILE).replace(b"PK\x01\x02", b"XX\x01\x02")
        self.post(broken)
        upload = Upload.objects.get()
        self.assertEqual(upload.status, Upload.Status.FAILED)
        self.assertTrue(upload.error)
        self.assertEqual(list(Path(self.incoming.name).iterdir()), [])

    def test_unexpected_errors_fail_the_upload_and_are_reraised(self):
        upload = Upload.objects.create(
            platform=self.platform, requested_at="2026-09-01", file_name="x.zip"
        )
        path = Path(self.incoming.name) / "x"
        path.write_bytes(b"data")
        with (
            mock.patch("ddp_tracker.ddps.tasks.parse", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
            self.assertLogs("ddp_tracker.ddps.tasks", "ERROR"),
        ):
            parse_upload.call(upload.pk, str(path))
        upload.refresh_from_db()
        self.assertEqual(upload.status, Upload.Status.FAILED)
        self.assertFalse(path.exists())

    @override_settings(DDP_MAX_UPLOAD_SIZE=10)
    def test_size_limit(self):
        response = self.post(make_zip(PROFILE))
        self.assertEqual(response.status_code, 200)
        self.assertIn("file", response.context["form"].errors)
        self.assertFalse(Upload.objects.exists())


class UploadPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="Instagram", slug="instagram")
        self.client.force_login(self.user)

    def test_list(self):
        parsed_upload(self.platform, PROFILE)
        response = self.client.get(reverse("ddps:uploads"))
        self.assertContains(response, "export.zip")

    def test_detail_links_the_review_and_flags_duplicates(self):
        first = parsed_upload(self.platform, PROFILE, register=True)
        second = parsed_upload(self.platform, PROFILE)
        response = self.client.get(first.get_absolute_url())
        self.assertContains(response, reverse("schemas:review", args=[first.pk]))
        response = self.client.get(second.get_absolute_url())
        self.assertContains(response, "Not yet added")
        self.assertContains(response, f"#{first.pk}")  # duplicate of the first upload

    def test_failed_and_pending_uploads(self):
        failed = Upload.objects.create(
            platform=self.platform,
            requested_at="2026-09-01",
            file_name="x.zip",
            status="failed",
            error="bad zip",
        )
        self.assertContains(self.client.get(failed.get_absolute_url()), "bad zip")
        pending = Upload.objects.create(
            platform=self.platform, requested_at="2026-09-01", file_name="y.zip"
        )
        self.assertContains(self.client.get(pending.get_absolute_url()), "every 2s")

    def test_status_polling(self):
        pending = Upload.objects.create(
            platform=self.platform, requested_at="2026-09-01", file_name="y.zip"
        )
        response = self.client.get(reverse("ddps:upload-status", args=[pending.pk]))
        self.assertContains(response, "Waiting to be parsed")
        pending.status = Upload.Status.DONE
        pending.save()
        response = self.client.get(reverse("ddps:upload-status", args=[pending.pk]))
        self.assertEqual(response["HX-Refresh"], "true")

    def test_model_helpers(self):
        upload = parsed_upload(self.platform, PROFILE)
        self.assertIn("Instagram · export.zip", str(upload))
        self.assertEqual(upload.warnings, [])
        empty = Upload(platform=self.platform, requested_at="2026-09-01")
        self.assertFalse(empty.duplicates().exists())


class RegisterCommandTests(TestCase):
    def test_registers_pending_uploads(self):
        platform = Platform.objects.create(name="Instagram", slug="instagram")
        upload = parsed_upload(platform, PROFILE)
        out = StringIO()
        call_command("register_uploads", stdout=out)
        upload.refresh_from_db()
        self.assertIsNotNone(upload.registered_at)
        self.assertIn("Registered 1 upload.", out.getvalue())
