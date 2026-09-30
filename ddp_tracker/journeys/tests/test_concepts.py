"""M1 and M2, the concept view: concepts across platforms, with labels per research field, and
what the uploads say about each (mockups/concepts.py)."""

from datetime import date
from typing import Any

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ddp_tracker.journeys.demo.spec import ANNOTATIONS
from ddp_tracker.journeys.mockups.concepts import (
    CONCEPTS,
    CONCEPTS_BY_SLUG,
    FIELDS,
    availability,
    resolve,
)
from ddp_tracker.journeys.tests.utils import SeededTestCase

LIST = reverse("journeys:concepts")
T = "/user_data_tiktok.json"


def slugs(response: Any) -> list[str]:
    return [card["concept"].slug for card in response.context["cards"]]


class ConceptDataTests(SimpleTestCase):
    def test_every_binding_names_an_annotation_of_the_demo_data(self) -> None:
        seeded = {(spec.platform, spec.name) for spec in ANNOTATIONS}
        for concept in CONCEPTS:
            for binding in concept.bindings:
                with self.subTest(concept=concept.slug, platform=binding.platform):
                    self.assertIn((binding.platform, binding.annotation), seeded)

    def test_themes_belong_to_fields_and_every_theme_is_used(self) -> None:
        themes = {theme.slug for field in FIELDS for theme in field.themes}
        used = {theme for concept in CONCEPTS for theme in concept.themes}
        self.assertEqual(used, themes)

    def test_slugs_are_unique(self) -> None:
        self.assertEqual(len(CONCEPTS_BY_SLUG), len(CONCEPTS))


class ConceptListWithoutDataTests(TestCase):
    def test_every_concept_by_relevance(self) -> None:
        response = self.client.get(LIST)
        expected = [c.slug for c in sorted(CONCEPTS, key=lambda c: -c.studies)]
        self.assertEqual(slugs(response), expected)
        self.assertContains(response, f"{len(CONCEPTS)} concepts")

    def test_it_says_that_the_demo_data_is_missing(self) -> None:
        response = self.client.get(LIST)
        self.assertContains(response, "seed_demo")
        self.assertFalse(any(card["availability"].known for card in response.context["cards"]))
        self.assertNotContains(response, "First seen")


class ConceptListTests(SeededTestCase):
    def test_a_theme_narrows_the_list(self) -> None:
        response = self.client.get(LIST, {"field": "communication", "theme": "news-politics"})
        self.assertEqual(
            set(slugs(response)), {"watched-video", "searched", "commented", "followed-account"}
        )
        self.assertContains(response, "4 concepts for News and politics")
        self.assertContains(response, 'aria-current="true"', count=1)

    def test_a_field_has_its_own_themes(self) -> None:
        response = self.client.get(LIST, {"field": "health"})
        self.assertContains(response, "Wellbeing and screen time")
        self.assertNotContains(response, "News and politics")
        # a theme of another field is ignored
        response = self.client.get(LIST, {"field": "communication", "theme": "wellbeing"})
        self.assertEqual(len(slugs(response)), len(CONCEPTS))

    def test_a_platform_narrows_the_list(self) -> None:
        found = slugs(self.client.get(LIST, {"platform": "instagram"}))
        self.assertIn("saw-ad", found)
        self.assertNotIn("off-platform-activity", found)
        # an unknown platform is ignored
        self.assertEqual(len(slugs(self.client.get(LIST, {"platform": "nope"}))), len(CONCEPTS))

    def test_sorting_by_name(self) -> None:
        found = slugs(self.client.get(LIST, {"sort": "name"}))
        names = [CONCEPTS_BY_SLUG[slug].name for slug in found]
        self.assertEqual(names, sorted(names))

    def test_the_choices_survive_in_the_theme_links(self) -> None:
        response = self.client.get(LIST, {"field": "health", "platform": "tiktok", "sort": "name"})
        self.assertContains(
            response, "?field=health&amp;theme=wellbeing&amp;platform=tiktok&amp;sort=name"
        )

    def test_a_card_says_what_the_uploads_show(self) -> None:
        found = availability(resolve(CONCEPTS_BY_SLUG["watched-video"]))
        self.assertTrue(found.known)
        # TikTok's older package is the first to have it; four uploads that count have it
        self.assertEqual(
            (found.first_seen, found.last_seen, found.uploads, found.pii),
            (date(2026, 3, 15), date(2026, 9, 15), 4, False),
        )
        self.assertTrue(availability(resolve(CONCEPTS_BY_SLUG["sent-message"])).pii)
        response = self.client.get(LIST)
        self.assertContains(response, "First seen")
        self.assertContains(response, "Personal data")

    def test_a_concept_resolves_to_its_paths(self) -> None:
        tiktok, instagram, facebook = resolve(CONCEPTS_BY_SLUG["watched-video"])
        self.assertEqual(
            (tiktok.name, instagram.name, facebook.name), ("TikTok", "Instagram", "Facebook")
        )
        # the path in use now first, then the older one
        self.assertEqual(
            [entry.location.path for entry in tiktok.locations],
            [
                f"{T}/Your Activity/Watch History/VideoList/[]",
                f"{T}/Activity/Video Browsing History/VideoList/[]",
            ],
        )
        current = tiktok.locations[0]
        self.assertEqual([field.name for field in current.fields], ["Date", "Link"])
        self.assertEqual(current.fields[0].profile.main_format, "%Y-%m-%d %H:%M:%S")
        self.assertEqual(current.languages, ["en"])
        self.assertEqual(current.examples[0], ("Date", "2026-09-01 08:15:42"))

    def test_availability_is_said_in_words(self) -> None:
        response = self.client.get(LIST)
        self.assertContains(response, "TikTok: not available")  # "Saw an ad" is Instagram only
        self.assertContains(response, reverse("journeys:concept", args=["watched-video"]))
        self.assertContains(response, reverse("schemas:platforms"))
        self.assertContains(response, "fictional")
