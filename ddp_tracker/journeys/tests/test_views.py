"""The landing page (pick a role) and the journey pages."""

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape  # pages escape apostrophes: compare with escaped text

from ddp_tracker.journeys.content import ROLES, ROLES_BY_SLUG
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

NO_DATA = "This database has no demo data yet"


def journey_url(slug):
    return reverse("journeys:journey", args=[slug])


class LandingPageTests(TestCase):
    def test_the_home_page_is_the_role_picker(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "journeys/index.html")
        self.assertEqual(reverse("journeys:index"), "/")
        self.assertContains(response, "<h1>DDP Tracker</h1>", html=True)
        self.assertContains(response, "What brings you here?")
        for role in ROLES:
            with self.subTest(role=role.slug):
                self.assertContains(response, f'href="{journey_url(role.slug)}"')
                self.assertContains(response, escape(f"I want to {role.card_line}."))

    def test_a_card_says_how_much_works_today(self):
        # the research engineer: two steps on pages that exist, three on mock-ups
        self.assertContains(
            self.client.get("/"),
            '<p class="card__hint role-card__meta">5 steps: 2 available today, 3 prototype</p>',
            html=True,
        )

    def test_it_works_for_everyone(self):
        for user in (
            None,
            User.objects.create_user("someone@example.org"),
            User.objects.create_user("staff@example.org", is_staff=True),
        ):
            if user is not None:
                self.client.force_login(user)
            self.assertEqual(self.client.get("/").status_code, 200)

    def test_an_empty_tracker_counts_nothing(self):
        response = self.client.get("/")
        self.assertEqual(
            response.context["counts"],
            [("Platforms", 0), ("Uploads", 0), ("Data points", 0), ("Annotations", 0)],
        )

    def test_the_previous_home_page_is_the_overview(self):
        self.assertEqual(reverse("core:index"), "/overview/")
        response = self.client.get("/overview/")
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(self.client.get("/"), 'href="/overview/"')

    def test_logging_in_and_out_leads_home(self):
        self.assertEqual(resolve_url(settings.LOGIN_REDIRECT_URL), "/")
        self.assertEqual(resolve_url(settings.LOGOUT_REDIRECT_URL), "/")


class SeededLandingPageTests(SeededTestCase):
    def test_the_figures_are_counted(self):
        counts = dict(self.client.get("/").context["counts"])
        # the held YouTube upload does not count
        self.assertEqual(
            (counts["Platforms"], counts["Uploads"], counts["Annotations"]), (4, 4, 28)
        )
        self.assertGreater(counts["Data points"], 500)


class JourneyPageTests(TestCase):
    def test_every_journey_shows_its_aim_and_steps(self):
        for role in ROLES:
            with self.subTest(role=role.slug):
                response = self.client.get(journey_url(role.slug))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"<h1>{role.name}</h1>", html=True)
                self.assertContains(response, escape(role.aim))
                self.assertContains(response, escape(role.audience))
                for step in role.steps:
                    self.assertContains(response, escape(step.title))
                    self.assertContains(response, escape(step.link_label))
                self.assertContains(response, "badge--available", count=role.available_count)
                self.assertContains(response, "badge--prototype", count=role.prototype_count)

    def test_a_step_says_what_it_needs_and_what_is_missing(self):
        response = self.client.get(journey_url("contributor"))
        self.assertContains(response, "Needs an account", count=3)
        self.assertContains(response, "Still missing:")
        self.assertContains(self.client.get(journey_url("curator")), "Staff only today")

    def test_a_prototype_step_can_name_the_page_that_exists_today(self):
        response = self.client.get(journey_url("researcher"))
        today = reverse("annotations:annotations", args=["tiktok"])
        self.assertContains(response, f'href="{today}"')
        self.assertContains(response, "Today: TikTok&#x27;s annotations")

    def test_the_features_a_journey_needs(self):
        response = self.client.get(journey_url("engineer"))
        self.assertContains(response, "Features this journey needs")
        for feature in ROLES_BY_SLUG["engineer"].features:
            self.assertContains(response, escape(feature.title))
        for label, css in (("Exists", "exists"), ("Partial", "partial"), ("Gap", "gap")):
            self.assertContains(
                response, f'<span class="badge badge--{css}">{label}</span>', html=True
            )
        self.assertContains(response, "raised at the hackathon")

    def test_the_other_journeys_are_one_click_away(self):
        response = self.client.get(journey_url("policy"))
        for role in ROLES:
            if role.slug != "policy":
                self.assertContains(response, f'href="{journey_url(role.slug)}"')

    def test_an_unknown_role_is_not_found(self):
        self.assertEqual(self.client.get(journey_url("nobody")).status_code, 404)

    def test_without_demo_data_the_page_says_so(self):
        self.assertContains(self.client.get(journey_url("engineer")), NO_DATA)


class SeededJourneyPageTests(SeededTestCase):
    def test_with_demo_data_there_is_no_notice(self):
        self.assertNotContains(self.client.get(journey_url("engineer")), NO_DATA)

    def test_everyone_gets_the_public_demo_link(self):
        response = self.client.get(journey_url("researcher"))
        self.assertContains(response, "Read TikTok&#x27;s annotation Watched video")

    def test_staff_get_the_review_of_the_demo_upload(self):
        review = "Open the review of the demo TikTok upload"
        self.assertNotContains(self.client.get(journey_url("engineer")), review)
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
        response = self.client.get(journey_url("engineer"))
        self.assertContains(response, review)
        # and the link works
        url = response.content.decode().split(review)[0].rsplit('href="', 1)[1].split('"')[0]
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_an_uploader_gets_their_held_upload(self):
        held = "Inspect the held demo upload"
        self.assertNotContains(self.client.get(journey_url("contributor")), held)
        self.client.force_login(User.objects.get(email=CURATOR_EMAIL))
        response = self.client.get(journey_url("contributor"))
        self.assertContains(response, held)
        url = response.content.decode().split(held)[0].rsplit('href="', 1)[1].split('"')[0]
        self.assertEqual(self.client.get(url).status_code, 200)
        # the curator's uploads are their own: no review of the admin's TikTok upload
        self.assertNotContains(response, "Open the review of the demo TikTok upload")


class NavigationTests(TestCase):
    """The header of every page: what exists in the main row, the mock-ups in a strip below."""

    def nav(self, response, css_class: str) -> str:
        return response.content.decode().split(f'<nav class="{css_class}"')[1].split("</nav>")[0]

    def test_the_brand_and_home_lead_to_the_landing_page(self):
        response = self.client.get(reverse("schemas:platforms"))
        self.assertContains(response, '<a class="site-header__brand" href="/">')
        self.assertContains(response, '<a href="/">Home</a>', html=True)

    def test_the_main_row_has_only_what_exists(self):
        main = self.nav(self.client.get("/"), "site-nav")
        for text in ("Home", "Explore", "Docs", "Contribute", "Log in"):
            self.assertIn(text, main)
        self.assertIn(f'href="{reverse("journeys:journey", args=["contributor"])}"', main)
        for text in ("Concepts", "Compare", "API", "prototype"):
            self.assertNotIn(text, main)

    def test_the_mockups_are_in_a_strip_of_their_own(self):
        strip = self.nav(self.client.get(reverse("schemas:platforms")), "prototype-nav")
        self.assertIn('aria-label="Prototype pages"', strip)
        self.assertIn("Prototype previews", strip)
        for name in ("journeys:concepts", "journeys:compare", "journeys:api"):
            self.assertIn(f'href="{reverse(name)}"', strip)
        self.assertNotIn("Curate", strip)  # staff only

    def test_staff_also_get_the_moderator_dashboard(self):
        self.client.force_login(User.objects.create_user("staff@example.org", is_staff=True))
        strip = self.nav(self.client.get("/"), "prototype-nav")
        self.assertIn(f'href="{reverse("journeys:moderate")}"', strip)
        self.assertIn("Curate", strip)

    def test_signed_in_people_keep_their_items(self):
        self.client.force_login(User.objects.create_user("someone@example.org"))
        main = self.nav(self.client.get("/"), "site-nav")
        for text in ("My uploads", "My suggestions", "Upload a DDP", "Log out"):
            self.assertIn(text, main)
        self.assertNotIn("Contribute", main)  # they have the upload button
