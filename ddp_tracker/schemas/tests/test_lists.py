"""A list and its item are both data points, each with its own annotation: the item carries the
meaning ("ID", "watched video"), the list's name is suggested from it ("List of …").
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.reviews.services import review
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.users.models import User

DATA = {"data.json": b'{"Ids": [1, 2, 3], "VideoList": [{"Date": "2024-01-01"}]}'}


class ListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.upload = parsed_upload(
            self.platform, DATA, requested_at=date(2026, 1, 1), register=True
        )
        self.ids = Location.objects.get(path="/data.json/Ids")
        self.item = Location.objects.get(path="/data.json/Ids/[]")

    def triage(self):
        return [item.location.path for item in review(self.upload).triage]

    def test_list_and_item_each_need_an_annotation(self):
        self.assertIn("/data.json/Ids", self.triage())
        create_annotation(self.item, "ID", self.user)
        self.assertIn("/data.json/Ids", self.triage())  # the list still needs its own
        page = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(page, "Ids[]")  # one row for the list and its item
        create_annotation(self.ids, "List of ID", self.user)
        self.assertNotIn("/data.json/Ids", self.triage())

    def test_the_item_first_then_the_list_in_its_own_step(self):
        self.client.force_login(self.user)
        url = reverse("schemas:triage", args=[self.item.pk])
        self.assertNotContains(self.client.get(url), "with_list")  # no "annotate both" option
        self.client.post(url, {"action": "new", "name": "ID", "with_list": "1"})
        annotations = dict(
            Location.objects.filter(annotation__isnull=False).values_list(
                "path", "annotation__name"
            )
        )
        self.assertEqual(annotations, {"/data.json/Ids/[]": "ID"})  # nothing implicit
        # the list's own dialog then suggests its name
        list_url = reverse("schemas:triage", args=[self.ids.pk])
        self.assertContains(self.client.get(list_url), 'value="List of ID"')

    def test_the_list_modal_suggests_the_name(self):
        create_annotation(self.item, "ID", self.user)
        self.client.force_login(self.user)
        modal = self.client.get(reverse("schemas:triage", args=[self.ids.pk]))
        self.assertContains(modal, 'value="List of ID"')

    def test_an_empty_list_doesnt_make_its_item_missing(self):
        create_annotation(self.item, "ID", self.user)
        empty = parsed_upload(
            self.platform,
            {"data.json": b'{"Ids": [], "VideoList": []}'},
            requested_at=date(2026, 6, 1),
            register=True,
        )
        self.assertNotIn("/data.json/Ids/[]", [m.location.path for m in review(empty).missing])
        gone = parsed_upload(
            self.platform,
            {"data.json": b'{"VideoList": []}'},
            requested_at=date(2026, 7, 1),
            register=True,
        )
        self.assertIn("/data.json/Ids/[]", [m.location.path for m in review(gone).missing])

    def test_representations_point_at_the_item(self):
        item_annotation = create_annotation(self.item, "ID", self.user)
        list_annotation = create_annotation(self.ids, "List of ID", self.user)
        self.client.force_login(self.user)
        modal = self.client.get(reverse("representations:add", args=[list_annotation.pk]))
        self.assertContains(modal, "Representations usually point at its item")
        self.assertContains(modal, item_annotation.get_absolute_url())
        item_modal = self.client.get(reverse("representations:add", args=[item_annotation.pk]))
        self.assertNotContains(item_modal, "usually point at its item")
