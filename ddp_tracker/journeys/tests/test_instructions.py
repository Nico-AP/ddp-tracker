"""M8, how to request a data download package: steps per platform, to be verified."""

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups.instructions import INSTRUCTIONS
from ddp_tracker.journeys.tests.utils import SeededTestCase


def page(slug: str) -> str:
    return reverse("journeys:request", args=[slug])


def text(content: bytes) -> str:
    """The page with its whitespace collapsed: sentences in templates wrap over lines."""
    return " ".join(content.decode().split())


class InstructionsWithoutDataTests(TestCase):
    def test_every_demo_platform_has_steps(self) -> None:
        for slug, instructions in INSTRUCTIONS.items():
            with self.subTest(platform=slug):
                response = self.client.get(page(slug))
                self.assertContains(response, "<ol")
                for step in instructions.steps:
                    self.assertContains(response, escape(step))
                self.assertContains(response, "To be verified by curators")
                self.assertContains(response, escape(instructions.choose))
                self.assertContains(response, escape(instructions.wait))
                self.assertContains(response, escape(instructions.receive))
                checked = instructions.last_checked
                self.assertContains(response, f"Last checked {checked.day} {checked:%B %Y}")

    def test_the_way_on(self) -> None:
        response = self.client.get(page("tiktok"))
        self.assertContains(response, "<h1>Request your data from TikTok</h1>", html=True)
        self.assertContains(response, f'href="{reverse("ddps:upload-create")}"')
        self.assertContains(response, reverse("docs", args=["guide/privacy/"]))
        self.assertContains(response, "Uploading needs an account")
        self.assertContains(response, "Request the same package twice")  # the pair hint
        for slug in INSTRUCTIONS:
            self.assertContains(response, page(slug))
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_it_says_what_the_upload_form_cannot_record(self) -> None:
        content = text(self.client.get(page("tiktok")).content)
        self.assertIn("other than app, browser or Portability API", content)

    def test_it_asks_for_corrections(self) -> None:
        content = text(self.client.get(page("youtube")).content)
        self.assertIn("Platforms change their menus", content)

    def test_a_platform_without_instructions(self) -> None:
        Platform.objects.create(name="Spotify", slug="spotify")
        response = self.client.get(page("spotify"))
        self.assertContains(response, "No instructions for Spotify yet")
        self.assertNotContains(response, "To be verified by curators")

    def test_an_unknown_platform_is_not_found(self) -> None:
        self.assertEqual(self.client.get(page("myspace")).status_code, 404)


class InstructionsTests(SeededTestCase):
    def test_the_upload_form_opens_with_the_platform_chosen(self) -> None:
        tiktok = Platform.objects.get(slug="tiktok")
        upload = reverse("ddps:upload-create")
        self.assertContains(
            self.client.get(page("tiktok")), f'href="{upload}?platform={tiktok.pk}"'
        )
