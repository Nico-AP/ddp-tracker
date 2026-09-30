"""M9, the moderator's dashboard: real queues of the platforms someone looks after."""

import re
from typing import Any

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL
from ddp_tracker.journeys.mockups.moderate import ASSIGNED
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

PAGE = reverse("journeys:moderate")


def text(content: bytes) -> str:
    """The page's words, without tags and with the whitespace collapsed: sentences in templates
    wrap over lines, and figures stand in bold."""
    return " ".join(re.sub(r"<[^>]+>", " ", content.decode()).split())


class DashboardWithoutDataTests(TestCase):
    def test_it_says_that_there_is_nothing_to_count(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "seed_demo")
        self.assertTrue(all(panel["queues"] is None for panel in response.context["panels"]))
        self.assertContains(response, "IsFastLane")  # the community's questions need no data
        self.assertEqual(response.context["elsewhere"], 0)
        page = text(response.content)
        self.assertIn("Instagram: /ads_information/ads_and_topics/videos_watched.json/[]", page)
        self.assertIn("5 answers", page)
        self.assertIn("No uploads wait on platforms you do not moderate", page)


class DashboardTests(SeededTestCase):
    def queues(self, panels: list[dict[str, Any]], slug: str) -> dict[str, Any]:
        return next(p["queues"] for p in panels if p["slug"] == slug)

    def test_the_queues_are_counted_from_the_database(self) -> None:
        response = self.client.get(PAGE)
        tiktok = self.queues(response.context["panels"], "tiktok")
        self.assertEqual(
            (
                tiktok["data_points"],
                tiktok["untriaged"],
                tiktok["suggestions"],
                tiktok["approvals"],
            ),
            (190, 177, 1, 0),
        )
        self.assertEqual(tiktok["unrepresented"], 17)
        self.assertEqual(len(tiktok["next"]), 5)
        self.assertEqual(tiktok["next"][0].seen, 2)  # in both TikTok packages
        self.assertGreater(self.queues(response.context["panels"], "instagram")["untriaged"], 100)
        # the held YouTube upload is not on "your" platforms
        self.assertEqual(response.context["elsewhere"], 1)
        page = text(response.content)
        self.assertIn("177 of 190 data points to triage", page)
        self.assertIn("1 upload waits on a platform you do not moderate", page)
        self.assertIn("in 2 uploads", page)
        self.assertNotContains(response, "seed_demo")

    def test_links_to_the_pages_that_exist(self) -> None:
        explorer = reverse("schemas:platform", args=["tiktok"])
        response = self.client.get(PAGE)
        self.assertContains(response, f"{explorer}?show=annotations")
        self.assertContains(response, f"{explorer}?show=representations")
        self.assertContains(response, f'href="{reverse("journeys:seed")}"')
        # the staff queues are linked for staff only
        queue = reverse("proposals:annotations")
        approvals = reverse("ddps:approvals")
        self.assertNotContains(response, f'href="{queue}')
        self.assertNotContains(response, f'href="{approvals}"')
        self.assertContains(response, "staff only today", count=2 * len(ASSIGNED))
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
        response = self.client.get(PAGE)
        self.assertContains(response, f'href="{queue}?platform=tiktok"')
        # one link per platform, and the header's "Approvals (1)"
        self.assertContains(response, f'href="{approvals}"', count=len(ASSIGNED) + 1)
        self.assertNotContains(response, "staff only today")

    def test_people_are_numbers(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "#12")
        self.assertNotContains(response, "@example.org")
