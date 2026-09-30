"""Every mock-up page: there, for everyone, with the banner, and part of a journey. What each
page shows has its own test file."""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ddp_tracker.journeys.mockups import MOCKUPS, find_platform, roles_using
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

BANNER = (
    "Prototype: this page shows fictional data to illustrate a planned feature. "
    "It does not work yet."
)


def mockup_urls():
    """A URL of every mock-up page, by its key in ``MOCKUPS``."""
    return {
        "concepts": reverse("journeys:concepts"),
        "concept": reverse("journeys:concept", args=["watched-video"]),
        "shortlist": reverse("journeys:shortlist"),
        "compare": reverse("journeys:compare"),
        "changes": reverse("journeys:changes", args=["tiktok"]),
        "api": reverse("journeys:api"),
        "snapshots": reverse("journeys:snapshots"),
        "request": reverse("journeys:request", args=["tiktok"]),
        "moderate": reverse("journeys:moderate"),
        "seed": reverse("journeys:seed"),
        "roles": reverse("journeys:roles"),
        "learn": reverse("journeys:learn", args=["tiktok"]),
    }


class RegistryTests(SimpleTestCase):
    def test_the_twelve_mockups(self):
        self.assertEqual(set(MOCKUPS), set(mockup_urls()))
        self.assertEqual(
            sorted(mockup.number for mockup in MOCKUPS.values()),
            sorted(f"M{number}" for number in range(1, 13)),
        )

    def test_every_mockup_is_reached_from_a_journey(self):
        for mockup in MOCKUPS.values():
            with self.subTest(mockup=mockup.key):
                self.assertTrue(roles_using(mockup))

    def test_their_url_names_exist(self):
        for mockup in MOCKUPS.values():
            for name in mockup.url_names:
                with self.subTest(name=name):
                    args = {"journeys:concept": ["x"]}.get(name) or (
                        ["tiktok"]
                        if name in {"journeys:changes", "journeys:request", "journeys:learn"}
                        else []
                    )
                    self.assertTrue(reverse(name, args=args).startswith("/prototype/"))


def check_every_page(case: TestCase) -> None:
    """Every page answers 200 with the banner, one heading, and where it fits, whoever asks."""
    visitors = {
        "signed out": None,
        "signed in": User.objects.create_user("someone@example.org"),
        "staff": User.objects.create_user("staff@example.org", is_staff=True),
    }
    for who, user in visitors.items():
        if user is not None:
            case.client.force_login(user)
        for key, url in mockup_urls().items():
            with case.subTest(who=who, page=key):
                response = case.client.get(url)
                case.assertEqual(response.status_code, 200)
                case.assertContains(response, BANNER)
                case.assertContains(response, "<h1", count=1)
                case.assertContains(response, "Where this fits")
                for role in roles_using(MOCKUPS[key]):
                    journey = reverse("journeys:journey", args=[role.slug])
                    case.assertContains(response, f'href="{journey}"')


class EmptyDatabaseTests(TestCase):
    def test_every_page_answers_for_everyone(self):
        check_every_page(self)

    def test_a_demo_platform_is_known_before_seeding(self):
        self.assertEqual(find_platform("tiktok"), ("TikTok", None))

    def test_an_unknown_platform_is_not_found(self):
        for name in ("journeys:changes", "journeys:request", "journeys:learn"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=["nope"])).status_code, 404)


class SeededDatabaseTests(SeededTestCase):
    def test_every_page_answers_for_everyone(self):
        check_every_page(self)

    def test_a_seeded_platform_is_found(self):
        name, platform = find_platform("tiktok")
        assert platform is not None
        self.assertEqual((name, platform.slug), ("TikTok", "tiktok"))
