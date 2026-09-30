"""M7, snapshots: dated releases to cite and to pin. All fictional."""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

from ddp_tracker.journeys.mockups.snapshots import DOI_PREFIX, SNAPSHOTS

PAGE = reverse("journeys:snapshots")


def text(content: bytes) -> str:
    """The page with its whitespace collapsed: sentences in templates wrap over lines."""
    return " ".join(content.decode().split())


class SnapshotDataTests(SimpleTestCase):
    def test_newest_first_and_monthly(self) -> None:
        versions = [snapshot.version for snapshot in SNAPSHOTS]
        self.assertEqual(versions, sorted(versions, reverse=True))
        self.assertEqual(versions[0], "2026.09")

    def test_a_doi_cannot_be_mistaken_for_a_real_one(self) -> None:
        for snapshot in SNAPSHOTS:
            self.assertTrue(snapshot.doi.startswith("10.0000/fictional"))
            self.assertTrue(snapshot.doi.startswith(DOI_PREFIX))
            # the citation links the DOI under the unregistered prefix, with no written tag
            self.assertIn(f"https://doi.org/{DOI_PREFIX}", snapshot.citation)
            self.assertNotIn("(fictional", snapshot.citation)


class SnapshotPageTests(TestCase):
    def test_the_releases(self) -> None:
        response = self.client.get(PAGE)
        self.assertEqual(list(response.context["snapshots"]), list(SNAPSHOTS))
        self.assertContains(response, "<h2>Releases</h2>", html=True)
        self.assertContains(response, '<th scope="col">Representations</th>', html=True)
        for snapshot in SNAPSHOTS:
            self.assertContains(response, snapshot.version)
            self.assertContains(response, snapshot.doi)
            for change in snapshot.changes:
                self.assertContains(response, escape(change))
        self.assertContains(response, "Tiktok Live is new")

    def test_citing_the_latest(self) -> None:
        response = self.client.get(PAGE)
        latest = SNAPSHOTS[0]
        self.assertEqual(response.context["latest"], latest)
        self.assertContains(response, escape(latest.citation))
        self.assertContains(response, f'data-copy="{escape(latest.citation)}"')
        self.assertContains(response, 'data-copied="Citation copied to the clipboard."')
        self.assertContains(response, 'role="status" data-copy-status')
        self.assertContains(response, "Copy the citation")
        self.assertNotContains(response, "copy-button")
        self.assertContains(response, "js/journeys.js")

    def test_pinning_for_machines(self) -> None:
        response = self.client.get(PAGE)
        page = text(response.content)
        self.assertContains(response, 'id="pin"')
        self.assertIn(f"curl {SNAPSHOTS[0].pinned_url}", page)
        self.assertIn('not for "latest"', page.replace("&quot;", '"'))
        self.assertContains(response, reverse("journeys:api") + "#licence")

    def test_downloads_are_not_there_yet(self) -> None:
        response = self.client.get(PAGE)
        page = text(response.content)
        self.assertIn("In the real feature, this would download the release.", page)
        self.assertEqual(page.count(" disabled>"), 3)
