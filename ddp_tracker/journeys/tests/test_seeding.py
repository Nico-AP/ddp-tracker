"""M10, seeding annotations from documentation, paired uploads and AI suggestions."""

import html
import re

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.journeys.mockups.seeding import AI_SUGGESTIONS, DOC_ENTRIES, PAIR_ROWS
from ddp_tracker.journeys.tests.utils import SeededTestCase

PAGE = reverse("journeys:seed")


def text(content: bytes) -> str:
    """The page's words, without tags, with entities read and the whitespace collapsed: sentences
    in templates wrap over lines."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", content.decode())).split())


class SeedingPageTests(TestCase):
    def test_official_documentation_is_the_first_tab(self) -> None:
        for url in (PAGE, PAGE + "?source=docs", PAGE + "?source=nope"):
            response = self.client.get(url)
            self.assertEqual(response.context["source"], "docs")
            self.assertContains(response, "Documented but not observed")
            self.assertContains(response, "Observed but not documented")
            self.assertContains(response, 'aria-current="page"', count=1)
        self.assertEqual(
            response.context["doc_summary"],
            [
                ("Matched", 3),
                ("Documented but not observed", 2),
                ("Observed but not documented", 2),
            ],
        )
        for entry in DOC_ENTRIES:
            self.assertContains(response, entry.documented or entry.path)
        page = text(response.content)
        self.assertIn(
            "3 matched, 2 documented but not observed, 2 observed but not documented.", page
        )
        self.assertIn("so that the gap between what a platform says", page)
        self.assertIn("Platform: Facebook. Source: Facebook's help pages on downloaded", page)

    def test_only_a_matched_entry_can_be_accepted(self) -> None:
        response = self.client.get(PAGE)
        page = text(response.content)
        self.assertIn("Accept Comments as an official annotation", page)
        self.assertEqual(page.count("as an official annotation"), 3)
        self.assertNotIn("Accept Payment history", page)
        self.assertContains(response, 'class="badge badge--official ms-0">Official</span>', count=5)

    def test_paired_uploads(self) -> None:
        response = self.client.get(PAGE + "?source=pairs")
        self.assertEqual(response.context["source"], "pairs")
        self.assertIn("Differs in: Account language", text(response.content))
        for row in PAIR_ROWS:
            self.assertContains(response, row.right)
            self.assertContains(response, row.evidence)
        self.assertContains(response, "Carry Watched video across")
        # three rows have an annotation to carry across, the fourth has none
        self.assertContains(response, "across</button>", count=3)
        self.assertNotContains(response, "Documented but not observed")

    def test_ai_suggestions_wait_for_a_person(self) -> None:
        response = self.client.get(PAGE + "?source=ai")
        self.assertContains(response, "Needs a human check", count=len(AI_SUGGESTIONS))
        self.assertIn(
            "never shown to the public before a person has checked", text(response.content)
        )
        for suggestion in AI_SUGGESTIONS:
            self.assertContains(response, f"Accept {suggestion.label}")
            self.assertContains(response, f"Reject {suggestion.label}")
        self.assertNotContains(response, "Carry Watched video across")

    def test_every_form_posts_to_the_page_with_its_source(self) -> None:
        for source in ("docs", "pairs", "ai"):
            response = self.client.get(PAGE + f"?source={source}")
            content = response.content.decode()
            forms = content.count('<form method="post"')
            self.assertGreater(forms, 0)
            self.assertEqual(content.count(f'action="{PAGE}"'), forms)
            self.assertEqual(
                content.count(f'<input type="hidden" name="source" value="{source}">'), forms
            )


class SeedingActionsTests(SeededTestCase):
    def test_a_button_explains_and_saves_nothing(self) -> None:
        before = Annotation.objects.count()
        response = self.client.post(PAGE, {"source": "pairs"}, follow=True)
        self.assertRedirects(response, PAGE + "?source=pairs")
        self.assertContains(response, "In the real feature, this would")
        self.assertContains(response, "Nothing was saved.")
        self.assertEqual(Annotation.objects.count(), before)

    def test_an_unknown_source_goes_back_to_the_documentation(self) -> None:
        response = self.client.post(PAGE, {"source": "https://example.org/"})
        self.assertRedirects(response, PAGE + "?source=docs")
