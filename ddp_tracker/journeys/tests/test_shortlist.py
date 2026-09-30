"""M3, the study shortlist: kept in the session, shared as a link, downloaded as a codebook and
as File Blueprints (mockups/shortlist.py)."""

import codecs
import csv
import io
import json
from typing import Any

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ddp_tracker.journeys.mockups.shortlist import SESSION_KEY, split_path
from ddp_tracker.journeys.tests.utils import SeededTestCase

PAGE = reverse("journeys:shortlist")
ADD = reverse("journeys:shortlist-add")
REMOVE = reverse("journeys:shortlist-remove")
CLEAR = reverse("journeys:shortlist-clear")
CODEBOOK = reverse("journeys:shortlist-codebook")
BLUEPRINT = reverse("journeys:shortlist-blueprint")
T = "/user_data_tiktok.json"
SHARED = "?c=watched-video&c=searched"


class SplitPathTests(SimpleTestCase):
    def test_the_file_and_the_keys_inside_it(self) -> None:
        self.assertEqual(
            split_path(f"{T}/Your Activity/Watch History/VideoList/[]"),
            ("user_data_tiktok.json", ["Your Activity", "Watch History", "VideoList", "[]"]),
        )
        self.assertEqual(
            split_path("/your_instagram_activity/likes/liked_posts.json/[]/timestamp"),
            ("your_instagram_activity/likes/liked_posts.json", ["[]", "timestamp"]),
        )
        self.assertEqual(split_path("/folder/only"), ("folder/only", []))


class ShortlistTests(TestCase):
    def chosen(self) -> list[dict[str, Any]]:
        return self.client.session.get(SESSION_KEY, [])

    def test_an_empty_shortlist_offers_a_start(self) -> None:
        response = self.client.get(PAGE)
        self.assertContains(response, "Your shortlist is empty")
        self.assertContains(response, f'href="{reverse("journeys:concepts")}"')
        self.assertContains(response, "?c=watched-video&amp;c=searched&amp;c=liked-content")
        self.assertNotContains(response, "Clear my shortlist")

    def test_adding_and_removing(self) -> None:
        response = self.client.post(ADD, {"concept": "watched-video"})
        self.assertRedirects(response, PAGE)
        self.client.post(ADD, {"concept": "searched", "note": "Exposure to news"})
        self.assertEqual(
            self.chosen(),
            [
                {"concept": "watched-video", "note": ""},
                {"concept": "searched", "note": "Exposure to news"},
            ],
        )
        page = self.client.get(PAGE)
        self.assertContains(page, "Watched a video")
        self.assertContains(page, "Exposure to news")
        self.assertContains(page, "Clear my shortlist")
        self.client.post(ADD, {"concept": "watched-video"})  # twice: still once
        self.assertEqual(len(self.chosen()), 2)
        self.client.post(REMOVE, {"concept": "watched-video"})
        self.assertEqual([entry["concept"] for entry in self.chosen()], ["searched"])
        self.client.post(CLEAR)
        self.assertEqual(self.chosen(), [])

    def test_a_note_can_be_changed_and_is_kept_when_adding_again(self) -> None:
        self.client.post(ADD, {"concept": "searched", "note": "First"})
        self.client.post(ADD, {"concept": "searched"})  # no note field: the note stays
        self.assertEqual(self.chosen()[0]["note"], "First")
        self.client.post(ADD, {"concept": "searched", "note": "x" * 400})
        self.assertEqual(len(self.chosen()[0]["note"]), 300)

    def test_only_known_concepts_and_only_by_post(self) -> None:
        self.assertEqual(self.client.post(ADD, {"concept": "nope"}).status_code, 400)
        self.assertEqual(self.client.post(ADD).status_code, 400)
        for url in (ADD, REMOVE, CLEAR):
            self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.chosen(), [])

    def test_it_returns_to_where_the_visitor_was_if_that_is_here(self) -> None:
        back = reverse("journeys:concepts") + "?field=health"
        response = self.client.post(ADD, {"concept": "searched", "next": back})
        self.assertRedirects(response, back)
        response = self.client.post(ADD, {"concept": "searched", "next": "https://example.org/"})
        self.assertRedirects(response, PAGE)
        for word in ("foo", "logout"):  # not a URL name either
            with self.subTest(next=word):
                response = self.client.post(ADD, {"concept": "searched", "next": word})
                self.assertRedirects(response, PAGE)

    def test_adding_says_so(self) -> None:
        response = self.client.post(ADD, {"concept": "searched"}, follow=True)
        self.assertContains(response, "Added to your shortlist: Searched.")

    def test_saving_a_note_says_so(self) -> None:
        self.client.post(ADD, {"concept": "searched"}, follow=True)  # its message shown
        response = self.client.post(ADD, {"concept": "searched", "note": "News"}, follow=True)
        self.assertContains(response, "Note saved for Searched.")
        self.assertNotContains(response, "Added to your shortlist")
        # a note for a concept not on the list yet: it is added
        response = self.client.post(ADD, {"concept": "logged-in", "note": "Time"}, follow=True)
        self.assertContains(response, "Added to your shortlist: Logged in.")

    def test_the_note_field_names_its_concept(self) -> None:
        self.client.post(ADD, {"concept": "searched"})
        response = self.client.get(PAGE)
        self.assertContains(response, '<span class="visually-hidden"> (Searched)</span>')
        self.assertContains(response, 'maxlength="300"')

    def test_a_shared_link_shows_its_own_list_and_leaves_mine_alone(self) -> None:
        self.client.post(ADD, {"concept": "logged-in"})
        response = self.client.get(PAGE + SHARED + "&c=nope")
        self.assertContains(response, "A shared shortlist")
        self.assertContains(response, "Watched a video")
        self.assertContains(response, 'href="/prototype/concepts/searched/"')
        self.assertNotContains(response, "Save note")  # read-only
        self.assertNotContains(response, "Clear my shortlist")
        self.assertContains(response, "Add these to my shortlist")
        self.assertEqual([entry["concept"] for entry in self.chosen()], ["logged-in"])

    def test_a_shared_shortlist_can_be_saved(self) -> None:
        self.client.post(ADD, {"concept": ["watched-video", "searched"]})
        self.assertEqual(len(self.chosen()), 2)

    def test_the_link_to_hand_over(self) -> None:
        self.client.post(ADD, {"concept": "watched-video"})
        self.client.post(ADD, {"concept": "searched"})
        response = self.client.get(PAGE)
        self.assertContains(
            response,
            'data-copy="http://testserver/prototype/shortlist/?c=watched-video&amp;c=searched"',
        )
        self.assertContains(response, f"{CODEBOOK}?c=watched-video&amp;c=searched")
        self.assertContains(response, "js/journeys.js")

    def test_the_copy_button_is_announced(self) -> None:
        self.client.post(ADD, {"concept": "searched"})
        response = self.client.get(PAGE)
        self.assertContains(response, 'role="status"')
        self.assertContains(response, "data-copy-status")

    def test_an_empty_database_says_how_to_get_data(self) -> None:
        response = self.client.get(PAGE + SHARED)
        self.assertContains(response, "No demo data in this database yet")


class ShortlistWithDataTests(SeededTestCase):
    def test_the_data_points_of_the_chosen_concepts(self) -> None:
        response = self.client.get(PAGE + SHARED)
        for text in (
            f"{T}/Your Activity/Watch History/VideoList/[]/Date",
            f"{T}/Activity/Video Browsing History/VideoList/[]/Link",  # the older variant too
            "/logged_information/search/your_search_history.json/searches_v2/[]/timestamp",
            "%Y-%m-%d %H:%M:%S",
            "UTC (assumed",
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertNotContains(response, "No demo data in this database yet")

    def test_the_codebook(self) -> None:
        response = self.client.get(CODEBOOK + SHARED)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(
            'filename="ddp-tracker-codebook-prototype.csv"', response["Content-Disposition"]
        )
        self.assertTrue(response.content.startswith(codecs.BOM_UTF8))  # a BOM, for Excel
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(
            list(rows[0]),
            [
                "concept",
                "platform",
                "annotation",
                "path",
                "type",
                "format",
                "personal_data",
                "tz_whos",
                "first_seen",
                "last_seen",
                "note",
                "source",
            ],
        )
        date = next(
            row
            for row in rows
            if row["path"] == f"{T}/Your Activity/Watch History/VideoList/[]/Date"
        )
        self.assertEqual(
            (date["concept"], date["platform"], date["annotation"], date["type"], date["format"]),
            ("Watched a video", "TikTok", "Watched video", "string", "%Y-%m-%d %H:%M:%S"),
        )
        self.assertEqual((date["first_seen"], date["personal_data"]), ("2026-09-15", "no"))
        self.assertIn("prototype", date["source"])
        self.assertEqual({row["platform"] for row in rows}, {"TikTok", "Instagram", "Facebook"})

    def test_the_codebook_of_my_own_shortlist_has_my_notes(self) -> None:
        self.client.post(ADD, {"concept": "sent-message", "note": "Social support"})
        rows = list(
            csv.DictReader(io.StringIO(self.client.get(CODEBOOK).content.decode("utf-8-sig")))
        )
        self.assertEqual({row["note"] for row in rows}, {"Social support"})
        self.assertEqual({row["personal_data"] for row in rows}, {"yes"})

    def test_the_blueprints(self) -> None:
        response = self.client.get(BLUEPRINT + SHARED)
        self.assertIn("ddm-blueprints-prototype.json", response["Content-Disposition"])
        data = json.loads(response.content)
        self.assertTrue(data["prototype"])
        self.assertIn("Illustrative", data["note"])
        by_name: dict[str, list[dict]] = {}
        for blueprint in data["blueprints"]:
            by_name.setdefault(blueprint["name"], []).append(blueprint)
        current, older = by_name["TikTok: Watched a video"]  # the path in use now first
        self.assertEqual(current["expected_file"], "user_data_tiktok.json")
        self.assertEqual(current["file_format"], "json")
        self.assertEqual(current["list_at"], ["Your Activity", "Watch History", "VideoList"])
        self.assertEqual(current["required_fields"], ["Date", "Link"])
        self.assertEqual(current["fields_to_keep"], ["Date", "Link"])
        self.assertEqual(older["list_at"], ["Activity", "Video Browsing History", "VideoList"])

    def test_a_variable_folder_becomes_a_pattern(self) -> None:
        data = json.loads(self.client.get(BLUEPRINT + "?c=sent-message").content)
        instagram = next(b for b in data["blueprints"] if b["platform"] == "instagram")
        self.assertEqual(
            instagram["expected_file"], "your_instagram_activity/messages/inbox/*/message_1.json"
        )
        self.assertEqual(instagram["list_at"], ["messages"])
        self.assertEqual(instagram["required_fields"], ["content"])
        self.assertTrue(instagram["personal_data"])

    def test_the_ethics_summary_counts_personal_data(self) -> None:
        response = self.client.get(PAGE + "?c=sent-message&c=searched")
        self.assertEqual(response.context["personal"], 3)  # the message text on three platforms
        self.assertContains(response, "flagged as personal data")

    def test_the_previews_are_on_the_page(self) -> None:
        response = self.client.get(PAGE + SHARED)
        self.assertContains(response, "concept,platform,annotation,path")
        self.assertContains(
            response, "&quot;expected_file&quot;: &quot;user_data_tiktok.json&quot;"
        )

    def test_concept_pages_add_to_the_shortlist(self) -> None:
        for url in (reverse("journeys:concepts"), reverse("journeys:concept", args=["searched"])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'action="{ADD}"')
                self.assertContains(response, 'name="concept" value="searched"')
                self.assertContains(response, "csrfmiddlewaretoken")
                self.assertContains(response, f'href="{PAGE}"')
