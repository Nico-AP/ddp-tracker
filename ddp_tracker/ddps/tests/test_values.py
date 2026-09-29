"""The uploader's own values (ddps/values.py): collected on upload, sealed with a key only the
uploader's browser holds, shown to them alone, and added to the examples only when they choose.
"""

import json
import tempfile
from datetime import date, timedelta
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.models import Platform, Upload, UploadValues
from ddp_tracker.ddps.values import cookie_name, split_values
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.users.models import User

EARLIER = {"profile.json": b'{"name": "Anna", "mail": "anna@example.org", "joined": "2024-01-01"}'}
MINE = {
    "profile.json": (
        b'{"name": "Fritzli", "mail": "fritz@example.com", "joined": "2024-02-02",'
        b' "bio": "Write me: fritz@example.com"}'
    )
}
NAME = "/profile.json/name"


class SplitValuesTests(TestCase):
    def test_takes_samples_and_ranges_out_and_masks_addresses(self):
        document = {
            "root": {
                "path": "",
                "children": [
                    {
                        "path": "/a.json",
                        "properties": {
                            "n": {"path": "/a.json/n", "range": {"min": 1, "max": 9}},
                            "note": {
                                "path": "/a.json/note",
                                "samples": {"values": ["Hi anna@x.com", 3], "redacted": False},
                            },
                        },
                        "items": {"path": "/a.json/[]", "samples": {"values": [True]}},
                    }
                ],
            }
        }
        found = split_values(document)
        self.assertEqual(found, {"/a.json/note": ["Hi axxx@x.xxx", 3], "/a.json/[]": [True]})
        text = json.dumps(document)
        self.assertNotIn("samples", text)
        self.assertNotIn("range", text)


class OwnValuesTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.uploader = User.objects.create_user("uploader")
        self.other = User.objects.create_user("other")
        self.staff = User.objects.create_user("admin", is_staff=True, is_superuser=True)
        parsed_upload(self.platform, EARLIER, requested_at=date(2026, 1, 1), register=True)
        incoming = tempfile.TemporaryDirectory()
        self.addCleanup(incoming.cleanup)
        settings = override_settings(DDP_INCOMING_DIR=incoming.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.uploader)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("ddps:upload-create"),
                {
                    "platform": self.platform.pk,
                    "requested_at": "2026-09-01",
                    "file_format": "zip",
                    "file": SimpleUploadedFile("export.zip", make_zip(MINE)),
                },
            )
        self.upload = Upload.objects.get(uploaded_by=self.uploader)
        self.name = Location.objects.get(path=NAME)
        self.review = reverse("reviews:review", args=[self.upload.pk])
        self.panel = reverse("reviews:location", args=[self.upload.pk, self.name.pk])

    def get(self, url, client=None, **params):
        return (client or self.client).get(url, params)

    def test_kept_sealed_and_out_of_the_document(self):
        self.assertIsNotNone(self.upload.registered_at)
        row = UploadValues.objects.get(upload=self.upload)
        self.assertNotIn(b"Fritzli", bytes(row.sealed))
        self.assertNotIn("Fritzli", json.dumps(self.upload.document))
        self.assertNotIn("Fritzli", json.dumps(list(self.upload.observations.values())))
        self.assertIn(cookie_name(self.upload), self.client.cookies)

    def test_the_uploader_sees_them_with_addresses_masked(self):
        # name and mail were in the earlier upload (Known), bio wasn't (New)
        page = self.get(self.review, tab="known")
        self.assertContains(page, '<span class="review-row__values">Fritzli</span>', html=True)
        self.assertContains(page, "fxxxx@xxxxxxx.xxx")  # a whole address
        self.assertNotContains(page, "fritz@example.com")
        page = self.get(self.review, tab="new")
        self.assertContains(page, "Write me: fxxxx@xxxxxxx.xxx")  # an address inside a text
        self.assertNotContains(page, "fritz@example.com")
        panel = self.get(self.panel)
        self.assertContains(panel, "Values in this file")
        self.assertContains(
            panel, '<code class="chip chip--value" title="Fritzli">Fritzli</code>', html=True
        )
        modal = self.get(reverse("schemas:triage", args=[self.name.pk]), upload=self.upload.pk)
        self.assertContains(modal, "Fritzli")
        row = self.get(reverse("reviews:row", args=[self.upload.pk, self.name.pk]))
        self.assertContains(row, "Fritzli")

    def test_nobody_else_sees_them_even_with_the_key(self):
        review_urls = (
            self.review,
            self.panel,
            reverse("reviews:row", args=[self.upload.pk, self.name.pk]),
        )
        triage = reverse("schemas:triage", args=[self.name.pk])
        for user in (self.other, self.staff):
            with self.subTest(user=user.username):
                client = Client()
                client.cookies = self.client.cookies  # even with the uploader's key
                client.force_login(user)
                responses = [self.get(triage, client, upload=self.upload.pk)]
                if user.is_staff:  # staff open the review, others don't reach it at all
                    responses += [self.get(url, client) for url in review_urls]
                else:
                    for url in review_urls:
                        self.assertEqual(self.get(url, client).status_code, 404)
                for response in responses:
                    self.assertNotContains(response, "Fritzli")
                    self.assertNotContains(response, "Values in this file")
                    self.assertNotContains(response, "Your values")  # the dialog's label
        self.client.logout()
        row = self.get(reverse("reviews:row", args=[self.upload.pk, self.name.pk]))
        self.assertEqual(row.status_code, 302)  # login first

    def test_unreadable_in_another_browser(self):
        client = Client()
        client.force_login(self.uploader)
        panel = self.get(self.panel, client)
        self.assertContains(panel, "Only readable in the browser you uploaded this DDP from")
        self.assertNotContains(panel, "Fritzli")
        self.assertNotContains(self.get(self.review, client), "Fritzli")

    def test_contribute_as_they_are(self):
        panel = self.get(self.panel)
        self.assertContains(panel, "Values in this file")
        self.assertNotContains(panel, "Add to examples")  # only once it's annotated
        create_annotation(self.name, "Display name", self.uploader)
        panel = self.get(self.panel)
        self.assertContains(panel, "Add to examples")
        self.assertContains(panel, '<code class="own-value" title="Fritzli">Fritzli</code>')
        self.assertNotContains(panel, 'name="value"')  # not editable
        url = reverse("reviews:add-examples", args=[self.upload.pk, self.name.pk])
        # only positions count: a posted text can't pass for an extracted value
        response = self.client.post(url, {"use": ["0", "7", "x"], "value": ["Made up"]})
        self.assertContains(response, "<code>Fritzli</code>", html=True)
        self.assertContains(response, "extracted")
        self.client.post(url, {"use": ["0"]})  # no duplicates
        self.name.refresh_from_db()
        self.assertEqual(self.name.example_values, [{"value": "Fritzli", "source": "extracted"}])
        joined = Location.objects.get(path="/profile.json/joined")
        other_url = reverse("reviews:add-examples", args=[self.upload.pk, joined.pk])
        self.client.post(other_url, {"use": ["0"]})
        joined.refresh_from_db()
        self.assertEqual(joined.example_values, [{"value": "2024-02-02", "source": "extracted"}])
        self.client.force_login(self.other)  # not theirs: as if it didn't exist
        self.assertEqual(self.client.post(url, {"use": ["0"]}).status_code, 404)
        # the uploader in another browser can't read them, so can't contribute them either
        client = Client()
        client.force_login(self.uploader)
        self.assertEqual(client.post(url, {"use": ["0"]}).status_code, 403)

    def test_extracted_examples_are_kept_or_removed_never_edited(self):
        url = reverse("reviews:add-examples", args=[self.upload.pk, self.name.pk])
        self.client.post(url, {"use": ["0"]})
        edit = reverse("schemas:examples", args=[self.name.pk])
        form = self.get(edit)
        self.assertContains(form, "Extracted from uploads")
        self.assertContains(
            form,
            '<input class="form-check-input" type="checkbox" name="extracted" id="id_extracted_0"'
            ' value="Fritzli" checked>',
            html=True,
        )
        forged = self.client.post(edit, {"extracted": ["Forged"], "example_values": ""})
        self.assertContains(forged, "Select a valid choice")  # can't be made up as "extracted"
        self.client.post(edit, {"extracted": ["Fritzli"], "example_values": "Jane"})
        self.name.refresh_from_db()
        self.assertEqual(
            self.name.example_values,
            [
                {"value": "Fritzli", "source": "extracted"},
                {"value": "Jane", "source": "user_input"},
            ],
        )
        self.client.post(edit, {"example_values": "Jane"})  # unchecked: removed
        self.name.refresh_from_db()
        self.assertEqual(self.name.example_values, [{"value": "Jane", "source": "user_input"}])

    def test_delete_my_values(self):
        url = reverse("ddps:upload-forget-values", args=[self.upload.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.uploader)
        response = self.client.post(url)
        self.assertRedirects(response, self.review)
        self.assertEqual(response.cookies[cookie_name(self.upload)].value, "")
        self.assertFalse(UploadValues.objects.exists())
        self.assertNotContains(self.get(self.panel), "Values in this file")

    def test_logging_out_deletes_the_keys(self):
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.cookies[cookie_name(self.upload)].value, "")
        self.client.force_login(self.uploader)
        self.assertContains(self.get(self.panel), "Only readable in the browser")

    def test_expired_values_are_gone(self):
        row = UploadValues.objects.get()
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
        self.assertNotContains(self.get(self.panel), "Values in this file")
        kept = parsed_upload(self.platform, EARLIER, requested_at=date(2026, 2, 1))
        UploadValues.objects.create(
            upload=kept, sealed=b"x", expires_at=timezone.now() + timedelta(days=1)
        )
        out = StringIO()
        call_command("purge_upload_values", stdout=out)
        self.assertIn("Deleted the values of 1 upload(s).", out.getvalue())
        self.assertEqual(list(UploadValues.objects.values_list("upload", flat=True)), [kept.pk])
