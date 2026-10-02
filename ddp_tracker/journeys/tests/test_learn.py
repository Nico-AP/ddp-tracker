"""M12, for learners: what a platform keeps about you, one example, a short exercise."""

import re

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups.learn import CATEGORIES, QUIZ
from ddp_tracker.journeys.tests.utils import SeededTestCase


def page(slug: str) -> str:
    return reverse("journeys:learn", args=[slug])


def text(content: bytes) -> str:
    """The page as words: tags stripped and whitespace collapsed (templates wrap sentences)."""
    return " ".join(re.sub(r"<[^>]+>", " ", content.decode()).split())


class LearnWithoutDataTests(TestCase):
    def test_the_categories_and_the_exercise_need_no_data(self) -> None:
        response = self.client.get(page("tiktok"))
        self.assertContains(response, "<h1>What TikTok keeps about you</h1>", html=True)
        for category in CATEGORIES["tiktok"]:
            self.assertContains(response, f"<h2>{category.name}</h2>", html=True)
            self.assertContains(response, escape(category.summary))
        self.assertContains(response, "seed_demo", count=1)
        self.assertContains(response, 'id="exercise"')
        self.assertContains(response, '<div class="quiz">')
        self.assertContains(response, "<details", count=len(QUIZ))
        for question in QUIZ:
            self.assertContains(response, escape(question.text))
            self.assertContains(response, escape(question.answer))
        self.assertNotContains(response, "kinds of information")
        self.assertNotContains(response, "One example, looked at closely")

    def test_it_explains_the_package_in_plain_words(self) -> None:
        content = text(self.client.get(page("facebook")).content)
        self.assertIn("When you ask Facebook for your data, you get a package", content)
        self.assertIn("Open a question to see its answer", content)

    def test_the_summary_leaves_out_the_repeated_name(self) -> None:
        summaries = [category.summary for category in CATEGORIES["tiktok"]]
        self.assertEqual(
            summaries[1], "The private messages you sent and received, with their text."
        )

    def test_an_unknown_platform_is_not_found(self) -> None:
        self.assertEqual(self.client.get(page("myspace")).status_code, 404)


class LearnTests(SeededTestCase):
    def test_categories_are_counted(self) -> None:
        response = self.client.get(page("tiktok"))
        counts = {category.name: count for category, count in response.context["categories"]}
        self.assertEqual(counts["Your messages"], 5)
        self.assertEqual(counts["Your profile and connections"], 55)
        self.assertGreater(counts["What you did"], 40)
        self.assertIn("5 kinds of information", text(response.content))
        self.assertNotContains(response, "seed_demo")

    def test_one_example_looked_at_closely(self) -> None:
        response = self.client.get(page("tiktok"))
        explained = response.context["explained"]
        self.assertEqual(explained["annotation"].name, "Watched video")
        self.assertEqual(explained["examples"][0], ("Date", "2026-09-01 08:15:42"))
        self.assertContains(response, "One video that was shown to the user")
        self.assertContains(response, '<th scope="col">Title</th>', html=True)
        self.assertContains(response, '<th scope="col">Value</th>', html=True)
        explorer = reverse("schemas:platform", args=["tiktok"])
        self.assertContains(response, f'href="{explorer}?q=VideoList"')

    def test_it_points_teachers_to_the_explainers(self) -> None:
        response = self.client.get(page("instagram"))
        self.assertIn("For teachers and study designers", text(response.content))
        self.assertContains(response, reverse("journeys:api") + "#explainers")
        self.assertContains(response, reverse("docs", args=[""]))
        self.assertContains(response, page("facebook"))
        self.assertContains(response, page("tiktok"))
        self.assertNotContains(response, page("youtube"))

    def test_a_platform_without_a_summary(self) -> None:
        response = self.client.get(page("youtube"))
        self.assertContains(response, "No summary for YouTube yet")
        self.assertContains(response, 'id="exercise"')
        self.assertNotContains(response, "kinds of information")

    def test_any_platform_of_the_database_gets_the_exercise(self) -> None:
        Platform.objects.create(name="Spotify", slug="spotify")
        response = self.client.get(page("spotify"))
        self.assertContains(response, "<h1>What Spotify keeps about you</h1>", html=True)
        self.assertContains(response, "No summary for Spotify yet")
        self.assertContains(response, "<details", count=len(QUIZ))
