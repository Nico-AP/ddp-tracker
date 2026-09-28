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

    def keys(self, response):
        return [row.key for group in response.context["tree"].groups for row in group.lines()]

    def test_unfiltered_is_the_most_common_format(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["counts"]["uploads"], 2)  # the two zips, not the CSV
        self.assertEqual(response.context["filter"].request_format, "json")
        self.assertFalse(response.context["filter"].is_active)

    def test_date_range(self):
        response = self.client.get(
            self.url, {"requested_from": "2025-01-01", "requested_to": "2026-06-30"}
        )
        self.assertEqual(self.keys(response), ["/new.json/k"])
        self.assertEqual(response.context["counts"]["uploads"], 1)
        self.assertContains(response, "Filtered:")

    def test_nothing_matches(self):
        self.assertContains(
            self.client.get(self.url, {"requested_to": "2020-01-01"}),
            "No uploads match this filter",
        )

    def test_language(self):
        self.assertEqual(
            self.keys(self.client.get(self.url, {"languages": ["en"]})), ["/old.json/k"]
        )

    def test_request_format_is_one_choice(self):
        response = self.client.get(self.url, {"request_format": "csv"})
        self.assertEqual(response.context["counts"]["uploads"], 1)
        (root,) = response.context["tree"].roots
        self.assertEqual(root.title, [("CSV file", True)])
        self.assertContains(response, "?request_format=json")  # the selector's other choice
        # the other filters keep the format; the format keeps the other filters
        languages = self.client.get(self.url, {"languages": ["en"], "request_format": "json"})
        self.assertContains(languages, 'name="request_format" value="json"')
        self.assertContains(languages, "?languages=en&amp;request_format=csv")

    def test_root_format_is_a_second_choice_within_a_request_format(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, 'aria-label="Uploaded file"')  # only zips: no choice
        parsed_file(
            self.platform, "posts.json", b'{"p": 1}', register=True
        )  # also requested as JSON
        response = self.client.get(self.url)
        self.assertEqual(response.context["filter"].root_format, "zip")  # the most common
        self.assertEqual(response.context["counts"]["uploads"], 2)
        self.assertContains(response, 'aria-label="Uploaded file"')
        self.assertContains(response, "?request_format=json&amp;root_format=json")
        single = self.client.get(self.url, {"request_format": "json", "root_format": "json"})
        (root,) = single.context["tree"].roots
        self.assertEqual(root.title, [("JSON file", True)])  # the file's format, not the request's
        self.assertEqual(self.keys(single), ["/p"])

    def test_filter_travels_into_htmx_urls(self):
        response = self.client.get(self.url, {"languages": ["de"]})
        self.assertContains(response, "?path=/new.json/k&languages=de&amp;request_format=json")
        groups = self.client.get(self.url, {"languages": ["en"]}, headers={"hx-request": "true"})
        self.assertTemplateUsed(groups, "schemas/tree/_groups.html")
        self.assertNotContains(groups, "new.json")  # new.json isn't in English exports

    def test_form_choices_and_query(self):
        rendered = FilterForm(platform=self.platform).as_div()
        for value in ('value=""', 'value="de"', 'value="en"'):
            self.assertIn(value, rendered)
        request = RequestFactory().get(
            "/", {"requested_from": "2026-01-01", "languages": ["de", "en"]}
        )
        schema_filter = SchemaFilter.from_request(request, self.platform)
        self.assertEqual(
            schema_filter.query,
            "requested_from=2026-01-01&languages=de&languages=en&request_format=json&root_format=zip",
        )
        self.assertEqual(
            schema_filter.with_format("csv"),
            "requested_from=2026-01-01&languages=de&languages=en&request_format=csv",
        )
        invalid = SchemaFilter.from_request(
            RequestFactory().get("/", {"requested_from": "nope"}), self.platform
        )
        self.assertEqual(invalid, SchemaFilter(request_format="json", root_format="zip"))
        self.assertEqual(
            [format_label("zip"), format_label("json"), format_label("")],
            ["ZIP archive", "JSON file", "file"],
        )
