"""The Explore page (schemas.views.platform_list): every platform with its figures."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform


class PlatformListTests(TestCase):
    def test_platforms_with_their_figures(self):
        platform = Platform.objects.create(name="Instagram", slug="instagram")
        parsed_upload(platform, {"a.json": b'{"name": "x", "bio": "y"}'}, register=True)
        parsed_upload(platform, {"a.json": b'{"name": "z"}'})  # not registered: doesn't count
        Platform.objects.create(name="Spotify", slug="spotify")
        response = self.client.get(reverse("schemas:platforms"))  # public
        self.assertContains(response, "<h1>Explore</h1>", html=True)
        self.assertContains(response, "Instagram")
        self.assertContains(response, "2 data points")
        self.assertContains(response, "1 upload")
        self.assertContains(response, "Last updated")
        self.assertContains(response, "No uploads yet")  # Spotify
        self.assertContains(response, platform.get_absolute_url())
        self.assertContains(response, reverse("annotations:annotations", args=["instagram"]))
        self.assertContains(response, reverse("representations:representations"))

    def test_no_platforms_yet(self):
        self.assertContains(self.client.get(reverse("schemas:platforms")), "No platforms yet")
