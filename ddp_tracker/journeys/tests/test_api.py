"""M6, the API overview: endpoints with examples, exports, access for language models."""

import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ddp_tracker.journeys.content import ROLES
from ddp_tracker.journeys.mockups.api import BASE, ENDPOINTS, EXPORTS, MCP_TOOLS

PAGE = reverse("journeys:api")


class ApiDataTests(SimpleTestCase):
    def test_every_example_answer_is_json(self):
        for endpoint in ENDPOINTS:
            with self.subTest(endpoint=endpoint.path):
                json.loads(endpoint.response)
                self.assertIn(BASE, endpoint.request)

    def test_the_address_is_an_example_address(self):
        self.assertIn("example.org", BASE)  # nothing points at the live site


class ApiPageTests(TestCase):
    def test_the_endpoints_with_their_examples(self):
        response = self.client.get(PAGE)
        for endpoint in ENDPOINTS:
            with self.subTest(endpoint=endpoint.path):
                self.assertContains(response, f'id="{endpoint.anchor}"')
                self.assertContains(response, endpoint.path)
        self.assertContains(response, "&quot;name&quot;: &quot;Watched video&quot;")
        self.assertContains(response, "django-ninja")

    def test_the_anchors_the_journeys_link_to(self):
        response = self.client.get(PAGE)
        fragments = {
            step.fragment
            for role in ROLES
            for step in role.steps
            if step.url_name == "journeys:api" and step.fragment
        }
        self.assertEqual(fragments, {"schema", "exports", "llm"})
        for fragment in fragments:
            self.assertContains(response, f'id="{fragment}"')

    def test_exports_language_models_and_licence(self):
        response = self.client.get(PAGE)
        for export in EXPORTS:
            self.assertContains(response, export.name)
        for name, _ in MCP_TOOLS:
            self.assertContains(response, name)
        self.assertContains(response, "llms.txt")
        self.assertContains(response, "CC BY 4.0")
        self.assertContains(response, reverse("journeys:shortlist"))
        self.assertContains(response, reverse("journeys:snapshots"))

    def test_explainers_for_participants(self):
        response = self.client.get(PAGE)
        self.assertContains(response, 'id="explainers"')
        self.assertContains(response, "donation tool")
