from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.users.models import User


class AnnotationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            self.platform, {"a.json": b'{"email": "a@b.ch"}'}, language="de", register=True
        )
        self.location = Location.objects.get(path="/a.json/email")
        self.annotation = create_annotation(self.location, "Email address", self.user)

    def test_list_and_detail_are_public(self):
        listing = self.client.get(reverse("annotations:annotations", args=["tiktok"]))
        self.assertContains(listing, "Email address")
        detail = self.client.get(self.annotation.get_absolute_url())
        self.assertContains(detail, "/a.json/email")
        self.assertContains(detail, "<td>de</td>", html=True)
        self.assertNotContains(detail, "Unlink")
        self.assertContains(
            self.client.get(reverse("annotations:details", args=[self.annotation.pk])),
            "Description",
        )

    def test_edit(self):
        url = reverse("annotations:edit", args=[self.annotation.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "Edit Email address")
        response = self.client.post(
            url, {"name": "Email", "description": "The account's address", "note": "Primary"}
        )
        self.assertContains(response, "The account&#x27;s address")
        self.annotation.refresh_from_db()
        self.assertEqual((self.annotation.name, self.annotation.updated_by), ("Email", self.user))

    def test_examples_are_shown_per_location(self):
        self.location.example_values = ["user@example.com"]
        self.location.save()
        self.assertContains(
            self.client.get(self.annotation.get_absolute_url()),
            "<code>user@example.com</code>",
            html=True,
        )

    def test_invalid_edit_shows_the_form(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("annotations:edit", args=[self.annotation.pk]), {"name": ""}
        )
        self.assertContains(response, "form__error")

    def test_unlink(self):
        self.client.force_login(self.user)
        self.assertContains(
            self.client.post(reverse("annotations:unlink", args=[self.location.pk])), "Unlinked"
        )
        self.location.refresh_from_db()
        self.assertIsNone(self.location.annotation)

    def test_str(self):
        self.assertEqual(str(self.annotation), "Email address")
        self.assertEqual(str(Annotation(name="x")), "x")
