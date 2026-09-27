import tempfile
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.checks import decide
from ddp_tracker.ddps.forms import COMMON_LANGUAGES, UploadForm, language_choices
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

    def post(self, data: bytes, name: str = "export.zip", file_format: str = "zip"):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("ddps:upload-create"),
                {
                    "platform": self.platform.pk,
                    "requested_at": "2026-09-01",
                    "language": "de",
                    "file_format": file_format,
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
        # the first upload of its platform and format waits for approval (ddps/checks.py)
        self.assertEqual(upload.plausibility, Upload.Plausibility.AWAITING)
        self.assertIsNone(upload.registered_at)
        self.assertFalse(Location.objects.exists())

    def test_unreadable_zip_fails_and_is_deleted(self):
        # passes the form's quick check (the archive's end record is intact), fails parsing
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
        self.assertContains(response, reverse("reviews:review", args=[first.pk]))
        decide(second)
        response = self.client.get(second.get_absolute_url())
        self.assertContains(response, "Not part of the collected schema")
        self.assertContains(response, "isn't counted again")
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


class LanguagePickerTests(TestCase):
    def test_common_languages_first_then_all_by_name(self):
        choices = language_choices()
        self.assertEqual(choices[0], ("", "Unknown"))
        (common_label, common), (all_label, others) = choices[1], choices[2]
        self.assertEqual((common_label, all_label), ("Common", "All languages"))
        self.assertEqual([code for code, _ in common], list(COMMON_LANGUAGES))
        names = [str(name) for _, name in others]
        self.assertEqual(names, sorted(names))
        self.assertNotIn("de", [code for code, _ in others])  # not listed twice
        self.assertIn("ja", [code for code, _ in others])

    def test_the_form_renders_groups_and_accepts_any_language(self):
        form = UploadForm()
        html = str(form["language"])
        self.assertIn('<optgroup label="Common">', html)
        self.assertLess(html.index(">German<"), html.index(">Afrikaans<"))
        mode = str(form["request_mode"])
        self.assertIn('<option value="" selected>Unknown</option>', mode)
        self.assertEqual(form.fields["request_mode"].clean(""), "")  # optional, like language
        field = form.fields["language"]
        for code in ("", "de", "ja"):
            with self.subTest(code=code):
                self.assertEqual(field.clean(code), code)
