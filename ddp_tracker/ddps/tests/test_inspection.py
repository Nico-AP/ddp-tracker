"""Inspecting held uploads (ddps/inspection.py): their structure, compared with the uploads that
count, for their uploader and staff only; nothing is registered by it.
"""

import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.checks import decide, peers_of, similarity
from ddp_tracker.ddps.inspection import KNOWN, MATCHED, NEW, inspect
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.ddps.tests.test_checks import UNRELATED
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.tests.test_workflow import ENGLISH, GERMAN
from ddp_tracker.users.models import User

DATE = "/activity/watch_history.json/[]/Date"
DATUM = "/your_activity/activity/watch_history.json/[]/Datum"


def statuses(inspection):
    found = {}

    def collect(line):
        if line.status:
            found[line.path] = line.status
        for child in line.children:
            collect(child)

    collect(inspection.root)
    return found


class InspectTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def test_known_matched_and_new(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        german = parsed_upload(self.platform, GERMAN, requested_at=date(2026, 6, 1))
        result = inspect(german, peers_of(german))
        found = statuses(result)
        self.assertEqual(found[DATUM], MATCHED)  # moved and translated
        (line,) = [child for child in _lines(result.root) if child.path == DATUM]
        assert line.match is not None
        self.assertEqual((line.match.path, line.match.reason), (DATE, "renamed"))
        self.assertTrue(result.has_peers)
        self.assertEqual(result.share, similarity(german))  # the same figure, explained
        self.assertEqual(sum(result.counts.values()), result.total)

    def test_new_and_missing(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        odd = parsed_upload(self.platform, UNRELATED)
        result = inspect(odd, peers_of(odd))
        self.assertEqual(set(statuses(result).values()), {NEW})
        self.assertEqual(result.share, 0.0)
        self.assertIn(DATE, result.missing)  # known, and not in this upload
        self.assertTrue(result.root.has_new)

    def test_the_same_upload_is_all_known(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        again = parsed_upload(self.platform, ENGLISH)
        result = inspect(again, peers_of(again))
        self.assertEqual(set(statuses(result).values()), {KNOWN})
        self.assertEqual((result.share, result.missing), (1.0, []))
        self.assertFalse(result.root.has_new)

    def test_nothing_to_compare_with(self):
        first = parsed_upload(self.platform, ENGLISH)
        result = inspect(first, [])
        self.assertFalse(result.has_peers)
        self.assertIsNone(result.share)
        self.assertEqual(set(statuses(result).values()), {NEW})
        self.assertEqual(result.root.name, "Upload")

    def test_unread_files_say_why(self):
        parsed_upload(self.platform, ENGLISH, register=True)
        odd = parsed_upload(self.platform, {"photos/p.bin": b"x"})
        result = inspect(odd, peers_of(odd))
        self.assertEqual(result.total, 0)
        self.assertIsNone(result.share)
        notes = [line.note for line in _lines(result.root) if line.note]
        self.assertTrue(any(note.startswith("not read: ") for note in notes))


def _lines(line):
    yield line
    for child in line.children:
        yield from _lines(child)


class InspectPageTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.uploader = User.objects.create_user("uploader")
        self.other = User.objects.create_user("other")
        self.staff = User.objects.create_user("admin", is_staff=True)
        parsed_upload(self.platform, ENGLISH, register=True)
        self.odd = parsed_upload(self.platform, UNRELATED, user=self.uploader)
        decide(self.odd)
        self.url = reverse("ddps:upload-inspect", args=[self.odd.pk])

    def test_uploader_and_staff_only(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)  # login first
        self.client.force_login(self.other)  # not theirs: as if it didn't exist
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.odd.get_absolute_url()).status_code, 404)
        for user in (self.uploader, self.staff):
            with self.subTest(user=user):
                self.client.force_login(user)
                page = self.client.get(self.url)
                self.assertContains(page, "0 % of its")
                self.assertContains(page, "albums")  # the upload's own keys
                self.assertContains(
                    page, '<span class="badge badge--changed">new</span>', html=True
                )
                self.assertContains(page, "watch_history.json")  # missing
                self.assertContains(self.client.get(self.odd.get_absolute_url()), self.url)

    def test_decisions_on_the_page(self):
        self.client.force_login(self.uploader)
        self.assertContains(self.client.get(self.url), "Yes, ask for approval")
        self.client.post(reverse("ddps:upload-decide", args=[self.odd.pk, "confirm"]))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url), ">Approve<")
        self.assertContains(self.client.get(reverse("ddps:approvals")), self.url)

    def test_registered_uploads_have_their_review_instead(self):
        counted = Upload.objects.get(registered_at__isnull=False)
        self.client.force_login(self.staff)
        url = reverse("ddps:upload-inspect", args=[counted.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(counted.get_absolute_url()), url)

    def test_inspecting_registers_nothing(self):
        before = (Location.objects.count(), Observation.objects.count())
        self.client.force_login(self.staff)
        self.client.get(self.url)
        self.assertEqual((Location.objects.count(), Observation.objects.count()), before)
        self.assertFalse(Location.objects.filter(path__contains="albums").exists())


class OwnValuesOnInspectionTests(TestCase):
    """The uploader sees their own values on the inspection; staff never do."""

    def setUp(self):
        self.platform = Platform.objects.create(name="Spotify", slug="spotify")
        self.uploader = User.objects.create_user("uploader")
        self.staff = User.objects.create_user("admin", is_staff=True)
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
                    "file": SimpleUploadedFile(
                        "export.zip", make_zip({"streams.json": b'[{"track": "Hey Jude"}]'})
                    ),
                },
            )
        self.upload = Upload.objects.get()  # the first of its kind: waits for approval
        self.url = reverse("ddps:upload-inspect", args=[self.upload.pk])

    def test_values_for_the_uploader_only(self):
        self.assertEqual(self.upload.plausibility, Upload.Plausibility.AWAITING)
        page = self.client.get(self.url)
        self.assertContains(page, "Nothing to compare with yet")
        self.assertContains(page, "Hey Jude")
        self.client.force_login(self.staff)
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Hey Jude")
