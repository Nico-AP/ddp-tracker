"""M11, roles and platforms: who may do what, where, without the Django admin."""

import html
import re

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.ddps.models import PathRule, Platform
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL
from ddp_tracker.journeys.mockups.roles import (
    EXAMPLE_RULE,
    EXAMPLE_RULE_NOTE,
    HUBS,
    PEOPLE,
    ROLE_DEFINITIONS,
)
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

PAGE = reverse("journeys:roles")


def text(content: bytes) -> str:
    """The page's words, without tags, with entities read and the whitespace collapsed: sentences
    in templates wrap over lines."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", content.decode())).split())


class RolesWithoutDataTests(TestCase):
    def test_roles_people_and_hubs(self) -> None:
        response = self.client.get(PAGE)
        for anchor in ('id="roles"', 'id="platforms"'):  # the administrator's journey links here
            self.assertContains(response, anchor)
        for definition in ROLE_DEFINITIONS:
            self.assertContains(response, definition.name)
            self.assertContains(response, html.escape(definition.may))
            self.assertContains(response, definition.today)
        for person in PEOPLE:
            self.assertContains(response, f"<td>{person.account}</td>", html=True)
        page = text(response.content)
        self.assertIn("#7 Moderator TikTok, Instagram", page)
        self.assertIn("#1 Administrator All", page)
        for hub in HUBS:
            self.assertIn(f"{hub.platform} {hub.hub} {hub.working_group}", page)
        self.assertIn("In the real feature, an administrator would change a role here", page)
        self.assertNotContains(response, "@example.org")

    def test_an_example_rule_when_there_is_none(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, EXAMPLE_RULE)
        self.assertContains(response, html.escape(EXAMPLE_RULE_NOTE))
        page = text(response.content)
        self.assertIn("This database has no path rule yet, so here is an example", page)
        self.assertIn("No demo data in this database yet", page)
        self.assertContains(response, "<code>uv run manage.py seed_demo</code>")

    def test_the_form_to_add_a_platform(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, '<form method="post"', count=1)
        self.assertContains(response, f'action="{PAGE}"', count=1)
        self.assertContains(response, 'for="platform-name">Name of the new platform</label>')
        self.assertContains(response, 'id="platform-name"')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, "<h3>Add a platform</h3>")
        self.assertContains(response, "Add platform</button>")

    def test_the_admin_is_named_without_links(self) -> None:
        response = self.client.get(PAGE)
        self.assertIn("Today this is done in the Django admin", text(response.content))
        self.assertNotContains(response, reverse("admin:ddps_platform_changelist"))


class RolesTests(SeededTestCase):
    def test_the_platforms_and_rules_are_the_databases(self) -> None:
        tiktok = Platform.objects.get(slug="tiktok")
        PathRule.objects.create(platform=tiktok, pattern="/user_data_tiktok.json/Some/Key *")
        response = self.client.get(PAGE)
        counts = {
            p.slug: (p.upload_count, p.data_point_count) for p in response.context["platforms"]
        }
        self.assertEqual(counts["tiktok"], (2, 190))
        self.assertEqual(counts["youtube"], (0, 0))
        self.assertIn("TikTok 2 190", text(response.content))
        self.assertContains(response, "<code>/user_data_tiktok.json/Some/Key *</code>")
        self.assertContains(response, "Variable key: rename matching keys")
        self.assertNotContains(response, EXAMPLE_RULE)
        self.assertNotContains(response, "No demo data in this database yet")

    def test_adding_a_platform_explains_and_saves_nothing(self) -> None:
        before = Platform.objects.count()
        response = self.client.post(PAGE, {"name": "Spotify"}, follow=True)
        self.assertRedirects(response, PAGE + "#platforms")
        self.assertContains(response, "In the real feature, this would add the platform")
        self.assertContains(response, "Nothing was saved.")
        self.assertEqual(Platform.objects.count(), before)
        self.assertFalse(Platform.objects.filter(name="Spotify").exists())

    def test_only_staff_get_links_to_the_admin(self) -> None:
        admin = reverse("admin:ddps_platform_changelist")
        self.assertNotContains(self.client.get(PAGE), admin)
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
        response = self.client.get(PAGE)
        self.assertContains(response, admin)
        self.assertContains(response, reverse("admin:ddps_pathrule_changelist"))
        self.assertNotContains(response, ADMIN_EMAIL)
