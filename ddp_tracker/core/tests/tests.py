from django.test import TestCase
from django.urls import reverse

from ddp_tracker.core.templatetags.core_tags import as_json
from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform


class IndexViewTests(TestCase):
    def test_renders_successfully(self):
        response = self.client.get(reverse("core:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")

    def test_lists_platforms_with_counts(self):
        platform = Platform.objects.create(name="Instagram", slug="instagram")
        parsed_upload(platform, {"a.json": b"{}"}, register=True)
        response = self.client.get(reverse("core:index"))
        self.assertContains(response, "Instagram")
        self.assertContains(response, "1 upload")


class HealthViewTests(TestCase):
    def test_returns_ok_status(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})


class TemplateFilterTests(TestCase):
    def test_template_filters(self):
        self.assertEqual(as_json({"b": 1, "a": "ä"}), '{\n  "a": "ä",\n  "b": 1\n}')
