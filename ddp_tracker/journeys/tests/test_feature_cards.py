"""The planned features as feature cards, in the hackathon's template."""

import re
from urllib.parse import urlsplit

from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils.html import escape

from ddp_tracker.journeys.feature_cards import CARDS

PAGE = reverse("journeys:features")


def text(content: bytes) -> str:
    """The page as words: tags stripped and whitespace collapsed (templates wrap sentences)."""
    return " ".join(re.sub(r"<[^>]+>", " ", content.decode()).split())


class FeatureCardDataTests(SimpleTestCase):
    def test_every_card_is_complete_and_leads_somewhere(self) -> None:
        self.assertEqual(len({card.slug for card in CARDS}), len(CARDS))
        for card in CARDS:
            with self.subTest(card=card.slug):
                for value in (
                    card.title,
                    card.problem,
                    card.solution,
                    card.user_group,
                    card.technical,
                    card.see_label,
                ):
                    self.assertTrue(value)
                    self.assertNotIn(chr(0x2014), value)  # no em dash
                resolve(urlsplit(card.see_url).path)


class FeatureCardPageTests(TestCase):
    def test_the_cards_follow_the_template(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "<h1>Feature cards</h1>", html=True)
        for label in (
            "Title",
            "Problem",
            "Description of solution",
            "User group",
            "Technical implementation",
        ):
            self.assertContains(
                response, f'<th scope="row">{label}</th>', count=len(CARDS), html=True
            )
        for card in CARDS:
            with self.subTest(card=card.slug):
                self.assertContains(response, f'<article class="proto-panel mb-4" id="{card.slug}"')
                self.assertContains(response, f"<h2>{escape(card.title)}</h2>", html=True)
                for value in (card.problem, card.solution, card.user_group, card.technical):
                    self.assertContains(response, escape(value))
                self.assertContains(response, f'href="{escape(card.see_url)}"')
                self.assertContains(response, f'href="#{card.slug}"', count=1)
        hackathon = [card for card in CARDS if card.from_hackathon_document]
        self.assertEqual(len(hackathon), 2)
        self.assertContains(response, "In the hackathon document", count=len(hackathon))

    def test_each_card_names_where_the_prototype_shows_it(self) -> None:
        content = text(self.client.get(PAGE).content)
        for card in CARDS:
            with self.subTest(card=card.slug):
                self.assertIn(f"See it in the prototype: {card.see_label}", content)

    def test_it_introduces_the_cards_as_proposals(self) -> None:
        content = text(self.client.get(PAGE).content)
        self.assertIn("Proposals for discussion, not decisions.", content)
        self.assertIn("so that they can be compared with the hackathon document", content)

    def test_it_is_a_page_of_the_app_not_a_mockup(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "<h1", count=1)
        self.assertNotContains(response, "prototype-banner")
        self.assertNotContains(response, "It does not work yet")

    def test_it_leads_back_to_the_landing_page_and_the_journeys(self) -> None:
        response = self.client.get(PAGE)
        home = reverse("journeys:index")
        self.assertContains(response, f'<a href="{home}">Back to the landing page</a>', html=True)
        self.assertContains(response, f'<a href="{home}#roles">Choose a journey</a>', html=True)

    def test_it_is_reached_from_the_landing_page_and_the_journeys(self) -> None:
        self.assertContains(self.client.get("/"), f'href="{PAGE}"')
        journey = reverse("journeys:journey", args=["researcher"])
        self.assertContains(self.client.get(journey), f'href="{PAGE}"')
