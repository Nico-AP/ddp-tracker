"""M9, the moderator's dashboard: real queues of the platforms someone looks after."""

import re
from typing import Any

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL
from ddp_tracker.journeys.mockups.moderate import ASSIGNED
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import ANNOTATION_KINDS
from ddp_tracker.users.models import User

PAGE = reverse("journeys:moderate")
QUEUE = reverse("proposals:annotations")
APPROVALS = reverse("ddps:approvals")


def text(content: bytes) -> str:
    """The page's words, without tags and with the whitespace collapsed: sentences in templates
    wrap over lines, and figures stand in bold."""
    return " ".join(re.sub(r"<[^>]+>", " ", content.decode()).split())


def queues(panels: list[dict[str, Any]], slug: str) -> dict[str, Any]:
    return next(p["queues"] for p in panels if p["slug"] == slug)


class DashboardWithoutDataTests(TestCase):
    def test_it_says_that_there_is_nothing_to_count(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "seed_demo")
        self.assertTrue(all(panel["queues"] is None for panel in response.context["panels"]))
        self.assertContains(response, "IsFastLane")  # the community's questions need no data
        self.assertIsNone(response.context["elsewhere"])  # staff only
        page = text(response.content)
        self.assertIn("Instagram: /ads_information/ads_and_topics/videos_watched.json/[]", page)
        self.assertIn("5 answers", page)
        self.assertIn("Today, only staff see how many uploads wait on platforms", page)

    def test_a_platform_without_counted_uploads(self) -> None:
        Platform.objects.create(name="TikTok", slug="tiktok")
        response = self.client.get(PAGE)
        self.assertEqual(queues(response.context["panels"], "tiktok")["data_points"], 0)
        page = text(response.content)
        self.assertIn("No counted uploads of TikTok yet.", page)
        self.assertNotIn("0 of 0", page)
        self.assertNotIn("Annotate next", page)
        self.assertNotIn("Every data point of TikTok has an annotation", page)


class DashboardTests(SeededTestCase):
    def as_staff(self) -> None:
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))

    def test_the_queues_are_counted_from_the_database(self) -> None:
        response = self.client.get(PAGE)
        tiktok = queues(response.context["panels"], "tiktok")
        self.assertEqual(
            (tiktok["data_points"], tiktok["untriaged"], tiktok["suggestions"]), (190, 177, 1)
        )
        self.assertEqual(tiktok["unrepresented"], 17)
        self.assertEqual(len(tiktok["next"]), 5)
        self.assertEqual(tiktok["next"][0].seen, 2)  # in both TikTok packages
        self.assertGreater(queues(response.context["panels"], "instagram")["untriaged"], 100)
        page = text(response.content)
        self.assertIn("177 of 190 data points to triage", page)
        self.assertIn("1 annotation suggestion to decide", page)
        self.assertIn("in 2 uploads", page)
        self.assertNotContains(response, "seed_demo")

    def test_only_annotation_suggestions_count(self) -> None:
        # the link opens the annotations queue, which does not list representation suggestions
        tiktok = Platform.objects.get(slug="tiktok")
        Proposal.objects.create(kind=Proposal.Kind.NEW_REPRESENTATION, platform=tiktok)
        response = self.client.get(PAGE)
        expected = Proposal.objects.filter(
            platform=tiktok, status=Proposal.Status.OPEN, kind__in=ANNOTATION_KINDS
        ).count()
        self.assertEqual(expected, 1)
        self.assertEqual(queues(response.context["panels"], "tiktok")["suggestions"], expected)

    def test_uploads_to_approve_are_for_staff_only(self) -> None:
        # as on the rest of the site: the header shows staff alone how many uploads wait
        for email in (None, CURATOR_EMAIL):
            with self.subTest(user=email):
                if email:
                    self.client.force_login(User.objects.get(email=email))
                response = self.client.get(PAGE)
                self.assertIsNone(queues(response.context["panels"], "tiktok")["approvals"])
                self.assertIsNone(response.context["elsewhere"])
                page = text(response.content)
                self.assertNotRegex(page, r"\d+ uploads? to approve")
                self.assertIn("Approving is for staff only today", page)
                self.assertNotIn("a platform you do not moderate", page)
                self.assertIn("Today, only staff see how many uploads wait", page)

    def test_staff_see_the_uploads_to_approve(self) -> None:
        self.as_staff()
        response = self.client.get(PAGE)
        self.assertEqual(queues(response.context["panels"], "tiktok")["approvals"], 0)
        # the held YouTube upload is not on "your" platforms
        self.assertEqual(response.context["elsewhere"], 1)
        page = text(response.content)
        self.assertIn("0 uploads to approve", page)
        self.assertIn("1 upload waits on a platform you do not moderate", page)
        # nothing to approve on your platforms: only the header's "Approvals (1)" links there
        self.assertContains(response, f'href="{APPROVALS}"', count=1)

        # the held upload moves to TikTok: the approvals list is worth a link now
        Upload.objects.filter(plausibility=Upload.Plausibility.AWAITING).update(
            platform=Platform.objects.get(slug="tiktok")
        )
        response = self.client.get(PAGE)
        self.assertEqual(queues(response.context["panels"], "tiktok")["approvals"], 1)
        self.assertEqual(response.context["elsewhere"], 0)
        page = text(response.content)
        self.assertIn("1 upload to approve", page)
        self.assertIn("No uploads wait on platforms you do not moderate", page)
        self.assertContains(response, f'href="{APPROVALS}"', count=2)

    def test_links_to_the_pages_that_exist(self) -> None:
        explorer = reverse("schemas:platform", args=["tiktok"])
        response = self.client.get(PAGE)
        self.assertContains(response, f"{explorer}?show=annotations")
        self.assertContains(response, f"{explorer}?show=representations")
        self.assertContains(response, f'href="{reverse("journeys:seed")}"')

    def test_the_staff_queues_are_linked_for_staff_only(self) -> None:
        for email in (None, CURATOR_EMAIL):
            with self.subTest(user=email):
                if email:
                    self.client.force_login(User.objects.get(email=email))
                response = self.client.get(PAGE)
                self.assertNotContains(response, f'href="{QUEUE}')
                self.assertNotContains(response, f'href="{APPROVALS}"')
                self.assertContains(response, "staff only today", count=2 * len(ASSIGNED))
        self.as_staff()
        response = self.client.get(PAGE)
        self.assertContains(response, f'href="{QUEUE}?platform=tiktok"')
        self.assertNotContains(response, "staff only today")

    def test_people_are_numbers(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "#12")
        self.assertNotContains(response, "@example.org")
