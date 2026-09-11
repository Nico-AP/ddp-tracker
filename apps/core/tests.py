from django.test import TestCase
from django.urls import reverse


class IndexViewTests(TestCase):
    def test_renders_successfully(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")


class HealthViewTests(TestCase):
    def test_returns_ok_status(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})
