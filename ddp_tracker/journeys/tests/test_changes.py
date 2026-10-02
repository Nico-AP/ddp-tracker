"""M5, a platform's changelog: what it added, moved, changed and removed between requests,
computed from the observations (mockups/changes.py)."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups.changes import timeline
from ddp_tracker.journeys.tests.utils import SeededTestCase

T = "/user_data_tiktok.json"
LIKE_DATE = f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date"


def page(slug: str) -> str:
    return reverse("journeys:changes", args=[slug])


class ChangelogWithoutDataTests(TestCase):
    def test_a_demo_platform_without_data_says_so(self) -> None:
        response = self.client.get(page("tiktok"))
        self.assertContains(response, "TikTok: changelog")
        self.assertContains(response, "seed_demo")


class ChangelogTests(SeededTestCase):
    def test_the_timeline_of_tiktok(self) -> None:
        september, march = timeline(Platform.objects.get(slug="tiktok"))  # newest first
        self.assertEqual(
            (march.upload.requested_at, september.upload.requested_at),
            (date(2026, 3, 15), date(2026, 9, 15)),
        )
        self.assertTrue(march.first)
        self.assertEqual((march.added, march.moved, march.changed, march.removed), ([], [], [], []))
        self.assertFalse(september.first)
        self.assertEqual(september.data_points, 156)
        # the live section is new; nothing else is
        self.assertEqual(len(september.added), 5)
        self.assertTrue(all("/Tiktok Live/" in path for path in september.added))
        # the renamed section's data points are recognised, not reported as new and removed
        self.assertIn(
            (
                f"{T}/Activity/Video Browsing History/VideoList/[]",
                f"{T}/Your Activity/Watch History/VideoList/[]",
            ),
            september.moved,
        )
        self.assertEqual(len(september.moved), 33)
        (change,) = september.changed
        self.assertEqual(
            (change.path, change.field, change.before, change.now),
            (LIKE_DATE, "format", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"),
        )
        self.assertEqual(
            september.removed, [f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived"]
        )

    def test_the_page(self) -> None:
        response = self.client.get(page("tiktok"))
        for text in (
            "TikTok: changelog",
            "5 added, 33 moved or renamed, 1 changed, 1 removed",
            "Tiktok Live",
            "Video Browsing History",
            "%Y-%m-%dT%H:%M:%SZ",
            "likesReceived",
            "First package",
            "and 25 more",  # 33 moved, 8 shown
            "In the real feature, this would",
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, f'href="{page("instagram")}"')

    def test_a_platform_with_one_package(self) -> None:
        (only,) = timeline(Platform.objects.get(slug="instagram"))
        self.assertTrue(only.first)
        self.assertContains(self.client.get(page("instagram")), "First package")

    def test_a_platform_without_a_package_that_counts(self) -> None:
        self.assertEqual(timeline(Platform.objects.get(slug="youtube")), [])
        self.assertContains(self.client.get(page("youtube")), "No package counts for YouTube yet")

    def test_it_never_names_an_uploader(self) -> None:
        response = self.client.get(page("tiktok"))
        self.assertNotContains(response, "@example.org")
