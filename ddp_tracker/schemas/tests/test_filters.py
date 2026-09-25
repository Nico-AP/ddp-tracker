from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse

from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.filters import FilterForm, SchemaFilter, format_label


class FilterTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(
            self.platform,
            {"old.json": b'{"k": 1}'},
            requested_at=date(2024, 5, 1),
            language="en",
            register=True,
        )
        parsed_upload(
            self.platform,
            {"new.json": b'{"k": 1}'},
            requested_at=date(2026, 5, 1),
            language="de",
            register=True,
        )
        parsed_file(self.platform, "single.csv", b"a,b\n1,2\n", register=True)
        self.url = reverse("schemas:platform", args=["tiktok"])

    def names(self, response):
        return [row["location"].name for row in response.context["rows"]]

    def test_unfiltered(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["counts"]["uploads"], 3)
        self.assertFalse(response.context["filter"].is_active)

    def test_date_range(self):
        response = self.client.get(
            self.url, {"requested_from": "2025-01-01", "requested_to": "2026-06-30"}
        )
        self.assertEqual(self.names(response), ["new.json"])
        self.assertEqual(response.context["counts"]["uploads"], 1)
        self.assertContains(response, "Filtered:")

    def test_nothing_matches(self):
        self.assertContains(
            self.client.get(self.url, {"requested_to": "2020-01-01"}),
            "No uploads match this filter",
        )

    def test_language(self):
        self.assertEqual(self.names(self.client.get(self.url, {"languages": ["en"]})), ["old.json"])

    def test_root_format(self):
        response = self.client.get(self.url, {"root_formats": ["csv"]})
        self.assertEqual(self.names(response), [None])  # the CSV's row node below the root
        self.assertContains(response, '<span class="badge badge--root">CSV file</span>', html=True)
        self.assertNotContains(
            response, '<span class="badge badge--root">ZIP archive</span>', html=True
        )

    def test_filter_travels_into_htmx_urls(self):
        response = self.client.get(self.url, {"languages": ["de"]})
        self.assertContains(response, "?path=/new.json&languages=de")
        children = self.client.get(
            reverse("schemas:children", args=["tiktok"]), {"path": "/new.json", "languages": ["en"]}
        )
        self.assertContains(children, "Empty.")  # new.json's keys aren't in English exports
        detail = self.client.get(
            reverse("schemas:location", args=["tiktok"]),
            {"path": "/new.json/k", "languages": ["de"]},
        )
        self.assertContains(detail, "Within the current filter")

    def test_form_choices_and_query(self):
        rendered = FilterForm(platform=self.platform).as_div()
        for value in ('value=""', 'value="de"', 'value="en"', 'value="csv"', 'value="zip"'):
            self.assertIn(value, rendered)
        request = RequestFactory().get(
            "/", {"requested_from": "2026-01-01", "languages": ["de", "en"]}
        )
        schema_filter = SchemaFilter.from_request(request, self.platform)
        self.assertEqual(schema_filter.query, "requested_from=2026-01-01&languages=de&languages=en")
        invalid = SchemaFilter.from_request(
            RequestFactory().get("/", {"requested_from": "nope"}), self.platform
        )
        self.assertEqual(invalid, SchemaFilter())
        self.assertEqual(
            [format_label("zip"), format_label("json"), format_label("")],
            ["ZIP archive", "JSON file", "file"],
        )
