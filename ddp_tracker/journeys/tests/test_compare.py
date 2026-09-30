"""M4, comparing platforms: which concepts each discloses, and how people get their data."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.journeys.mockups.compare import FACTS
from ddp_tracker.journeys.mockups.concepts import CONCEPTS
from ddp_tracker.journeys.tests.utils import SeededTestCase

PAGE = reverse("journeys:compare")


def text(content: bytes) -> str:
    """The page with its whitespace collapsed: sentences in templates wrap over lines."""
    return " ".join(content.decode().split())


class CompareWithoutDataTests(TestCase):
    def test_the_matrix_needs_no_data(self) -> None:
        response = self.client.get(PAGE)
        rows = dict(response.context["matrix"])
        by_slug = {concept.slug: cells for concept, cells in rows.items()}
        # platforms in the order facebook, instagram, tiktok, youtube
        self.assertEqual(by_slug["saw-ad"], [False, True, False, False])
        self.assertEqual(by_slug["off-platform-activity"], [True, False, True, False])
        self.assertEqual(len(rows), len(CONCEPTS))
        self.assertContains(response, "seed_demo")
        self.assertTrue(all(panel["figures"] is None for panel in response.context["panels"]))

    def test_yes_and_no_are_words(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "matrix__yes")
        self.assertContains(response, ">Yes<")
        self.assertContains(response, ">No<")

    def test_the_facts_stand_in_every_panel(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "Ways to request", count=len(FACTS))
        self.assertContains(response, "Google Takeout")
        self.assertIn("6 documented but not observed, 14 observed but not", text(response.content))


class CompareTests(SeededTestCase):
    def test_the_panels_mix_fictional_facts_and_real_figures(self) -> None:
        response = self.client.get(PAGE)
        panels = {panel["facts"].slug: panel for panel in response.context["panels"]}
        self.assertEqual(set(panels), {facts.slug for facts in FACTS})
        tiktok = panels["tiktok"]
        self.assertEqual((tiktok["figures"]["uploads"], tiktok["figures"]["annotations"]), (2, 12))
        self.assertEqual(tiktok["figures"]["data_points"], 190)
        self.assertEqual(tiktok["figures"]["last_requested"], date(2026, 9, 15))
        self.assertEqual(tiktok["disclosed"], 8)
        self.assertEqual(panels["youtube"]["figures"]["uploads"], 0)  # its upload is held
        self.assertContains(response, "8 of 9")
        page = text(response.content)
        self.assertIn("In this tracker: 2 uploads, 190 data points, 12 annotations", page)
        self.assertIn("last requested 15 September 2026", page)
        self.assertIn("YouTube has no package that counts yet", page)
        self.assertIn("In this tracker: no package from YouTube counts yet", page)
        self.assertNotContains(response, "seed_demo")

    def test_it_links_onwards(self) -> None:
        response = self.client.get(PAGE)
        for url in (
            reverse("journeys:concept", args=["saw-ad"]),
            reverse("schemas:platform", args=["tiktok"]),
            reverse("journeys:changes", args=["tiktok"]),
            reverse("journeys:seed") + "?source=docs",
        ):
            self.assertContains(response, url)
