from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_tracker.core.templatetags.core_tags import as_json
from ddp_tracker.ddps.models import Platform
from ddp_tracker.users.models import User


class IndexViewTests(TestCase):
    def test_renders_successfully(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")

    def test_platforms_are_on_the_explore_page(self):
        Platform.objects.create(name="Instagram", slug="instagram")
        response = self.client.get(reverse("core:index"))
        self.assertNotContains(response, "Instagram")  # listed on the Explore page instead
        explore = reverse("schemas:platforms")
        self.assertContains(response, f'<a href="{explore}">Explore</a>', html=True)  # header
        self.assertContains(response, f'href="{explore}"', count=4)  # header + three cards

    def test_signed_out_explore_and_how_to_contribute(self):
        response = self.client.get(reverse("core:index"))
        for url in (
            reverse("representations:representations"),
            reverse("representations:vocabulary"),
            f'href="{reverse("docs", args=[""])}"',
        ):
            self.assertContains(response, url)
        login = reverse("account_login")
        self.assertContains(response, f"{login}?next=/uploads/new/")
        self.assertContains(response, "Sign in to upload")
        self.assertNotContains(response, reverse("account_signup"))  # by invitation
        self.assertNotContains(response, "Curate")
        self.assertNotContains(response, reverse("proposals:mine"))
        self.assertNotContains(response, "inert")

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=True)
    def test_signup_link_when_registration_is_open(self):
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, reverse("account_signup"))

    def test_signed_in_contributors(self):
        self.client.force_login(User.objects.create_user("someone@example.org"))
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, f'href="{reverse("ddps:upload-create")}"')
        self.assertNotContains(response, "Sign in to upload")
        self.assertContains(response, "suggestions that staff review")
        self.assertContains(response, reverse("proposals:mine"))
        self.assertNotContains(response, "Curate")

    def test_staff_get_their_queues(self):
        self.client.force_login(User.objects.create_user("admin@example.org", is_staff=True))
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, "Curate")
        self.assertContains(response, "Approvals (0)")
        self.assertContains(response, reverse("ddps:approvals"))
        self.assertContains(response, reverse("proposals:representations"))
        self.assertContains(response, "Your changes apply right away")


class DevBannerTests(TestCase):
    banner = "This is a development version and only open to invited users."

    def test_on_every_page_by_default(self):
        for name in ("core:index", "schemas:platforms", "account_login"):
            self.assertContains(self.client.get(reverse(name)), self.banner)

    @override_settings(DEV_BANNER=False)
    def test_switched_off(self):
        self.assertNotContains(self.client.get(reverse("core:index")), self.banner)


@override_settings(PRIVATE_MODE=True)
class PrivateModeTests(TestCase):
    def test_signed_out_landing_page_is_locked(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="landing-locked" inert')
        self.assertContains(response, f'<a href="{reverse("account_login")}">Log in</a>', html=True)
        self.assertContains(
            response,
            f'<a class="btn btn-primary" href="{reverse("account_login")}">Log in</a>',
            html=True,
        )
        explore = reverse("schemas:platforms")
        self.assertNotContains(response, f'<a href="{explore}">Explore</a>', html=True)
        self.assertNotContains(response, "These need an account")

    def test_signed_out_everything_else_needs_a_login(self):
        login = reverse("account_login")
        for url in (
            reverse("schemas:platforms"),
            reverse("representations:representations"),
            reverse("representations:vocabulary"),
            reverse("docs", args=[""]),
        ):
            self.assertRedirects(
                self.client.get(url), f"{login}?next={url}", fetch_redirect_response=False
            )

    def test_signed_out_can_still_log_in(self):
        for name in ("account_login", "account_reset_password", "core:health"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_signed_in_users_see_everything(self):
        self.client.force_login(User.objects.create_user("someone@example.org"))
        response = self.client.get(reverse("core:index"))
        self.assertNotContains(response, "inert")
        explore = reverse("schemas:platforms")
        self.assertContains(response, f'<a href="{explore}">Explore</a>', html=True)
        self.assertEqual(self.client.get(explore).status_code, 200)


class HealthViewTests(TestCase):
    def test_returns_ok_status(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})


class TemplateFilterTests(TestCase):
    def test_template_filters(self):
        self.assertEqual(as_json({"b": 1, "a": "ä"}), '{\n  "a": "ä",\n  "b": 1\n}')
