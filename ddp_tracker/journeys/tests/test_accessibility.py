"""What every page of the app must get right for people who use a keyboard or a screen
reader: one main heading, headings in order, tables with header cells, fields with labels,
links and buttons with text, and a breadcrumb trail that names the page. Checked on the
rendered pages, with the demo data, for a visitor and for staff (who see a few more links)."""

import re
from collections.abc import Iterator
from html import unescape
from html.parser import HTMLParser
from typing import Any

from django.test import SimpleTestCase
from django.urls import reverse

from ddp_tracker.journeys.content import ROLES
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL
from ddp_tracker.journeys.mockups.shortlist import SOURCE
from ddp_tracker.journeys.mockups.snapshots import DOI_PREFIX
from ddp_tracker.journeys.tests.test_mockups import mockup_urls
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

# the one sentence that says the data is made up (the banner), and two that keep the word: the
# line the downloaded files carry (previewed on the shortlist) and the DOI prefix
BANNER = "Prototype: this page shows fictional data to illustrate a planned feature."
FICTIONAL = re.compile(r"made[ -]up|fictional|invented|not real|imaginary", re.IGNORECASE)


class Outline(HTMLParser):
    """What the checks need from a page: its headings, tables, form fields and labels, and
    the links and buttons that have no text."""

    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []  # levels, in order
        self.header_cells: list[int] = []  # per table, in order: its th with a scope
        self.fields: list[str | None] = []  # ids of visible fields ("" if none, None: aria-label)
        self.labels: set[str] = set()  # the ids that labels are for
        self.unnamed: list[str] = []  # links and buttons without text or an aria-label
        self._open: list[list[Any]] = []  # [tag, has a name] of the links and buttons we are in

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        elif tag == "table":
            self.header_cells.append(0)
        elif tag == "th" and found.get("scope") in {"col", "row"} and self.header_cells:
            self.header_cells[-1] += 1
        elif tag == "label":
            self.labels.add(found.get("for") or "")
        elif tag in {"select", "textarea"} or (
            tag == "input" and found.get("type") not in {"hidden", "submit", "button"}
        ):
            self.fields.append(None if found.get("aria-label") else (found.get("id") or ""))
        if tag in {"a", "button"}:
            self._open.append([tag, bool(found.get("aria-label"))])

    def handle_data(self, data: str) -> None:
        if self._open and data.strip():
            self._open[-1][1] = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "button"} and self._open:
            opened, named = self._open.pop()
            if not named:
                self.unnamed.append(opened)


class Crumbs(HTMLParser):
    """A page's breadcrumb trail (the items of its ``nav`` named "Breadcrumb") and the text of
    its main heading."""

    def __init__(self) -> None:
        super().__init__()
        self.trails = 0  # breadcrumb navs
        self.lists: list[str] = []  # the list tags inside them
        self.items: list[dict[str, Any]] = []  # {"text", "link", "current"}
        self.heading = ""
        self._in_trail = False
        self._in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if tag == "nav" and found.get("aria-label") == "Breadcrumb":
            self.trails += 1
            self._in_trail = True
        elif self._in_trail and tag in {"ol", "ul"}:
            self.lists.append(tag)
        elif self._in_trail and tag == "li":
            self.items.append({"text": "", "link": False, "current": found.get("aria-current")})
        elif self._in_trail and tag == "a" and self.items:
            self.items[-1]["link"] = True
        elif tag == "h1":
            self._in_heading = True

    def handle_data(self, data: str) -> None:
        if self._in_trail and self.items:
            self.items[-1]["text"] += data
        elif self._in_heading:
            self.heading += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._in_trail = False
        elif tag == "h1":
            self._in_heading = False


def words(text: str) -> str:
    return " ".join(text.split())


def page_text(html: str) -> str:
    """The words a reader sees: no tags, no scripts."""
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.DOTALL)
    return words(unescape(re.sub(r"<[^>]+>", " ", html)))


def pages() -> dict[str, str]:
    urls = {"landing": "/", "features": reverse("journeys:features")}
    urls |= {
        f"journey {role.slug}": reverse("journeys:journey", args=[role.slug]) for role in ROLES
    }
    urls |= {f"mock-up {key}": url for key, url in mockup_urls().items()}
    urls["shortlist with concepts"] = reverse("journeys:shortlist") + "?c=watched-video&c=searched"
    urls["seed pairs"] = reverse("journeys:seed") + "?source=pairs"
    urls["seed ai"] = reverse("journeys:seed") + "?source=ai"
    return urls


class AccessibilityTests(SeededTestCase):
    def rendered(self) -> Iterator[tuple[str, str]]:
        """Every page, first as a visitor and then as staff."""
        for who in ("visitor", "staff"):
            if who == "staff":
                self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
            for name, url in pages().items():
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, name)
                yield f"{name} ({who})", response.content.decode()

    def outlines(self) -> Iterator[tuple[str, Outline]]:
        for name, html in self.rendered():
            outline = Outline()
            outline.feed(html)
            yield name, outline

    def test_one_main_heading_and_no_skipped_level(self) -> None:
        for name, outline in self.outlines():
            with self.subTest(page=name):
                self.assertEqual(outline.headings.count(1), 1)
                self.assertEqual(outline.headings[0], 1)
                for before, after in zip(outline.headings, outline.headings[1:], strict=False):
                    self.assertLessEqual(after, before + 1, outline.headings)

    def test_tables_have_header_cells(self) -> None:
        for name, outline in self.outlines():
            with self.subTest(page=name):
                for count in outline.header_cells:
                    self.assertGreater(count, 0, outline.header_cells)

    def test_fields_have_labels(self) -> None:
        for name, outline in self.outlines():
            with self.subTest(page=name):
                for field in outline.fields:
                    if field is not None:  # None: it has an aria-label
                        self.assertIn(field, outline.labels - {""})

    def test_links_and_buttons_have_text(self) -> None:
        for name, outline in self.outlines():
            with self.subTest(page=name):
                self.assertEqual(outline.unnamed, [])

    def test_the_breadcrumb_names_the_page(self) -> None:
        for name, html in self.rendered():
            with self.subTest(page=name):
                crumbs = Crumbs()
                crumbs.feed(html)
                if name.startswith("landing "):  # the home page itself
                    self.assertEqual(crumbs.trails, 0)
                    continue
                self.assertEqual(crumbs.trails, 1)
                self.assertEqual(crumbs.lists, ["ol"])
                texts = [words(item["text"]) for item in crumbs.items]
                self.assertEqual(texts[0], "Home")
                self.assertTrue(crumbs.items[0]["link"])
                for text in texts:
                    self.assertTrue(text[:1].isupper(), texts)
                last = crumbs.items[-1]
                self.assertEqual(last["current"], "page")
                self.assertFalse(last["link"])
                self.assertEqual(texts[-1], words(crumbs.heading))
                for item in crumbs.items[:-1]:
                    self.assertIsNone(item["current"])

    def test_the_banner_alone_says_the_data_is_made_up(self) -> None:
        # Hekmat, at the Phase 3 check-in: no fictional labels or remarks next to things
        for name, html in self.rendered():
            with self.subTest(page=name):
                text = page_text(html)
                for kept in (BANNER, SOURCE, DOI_PREFIX):
                    text = text.replace(kept, "")
                self.assertEqual(FICTIONAL.findall(text), [])


class OutlineTests(SimpleTestCase):
    """The checks above catch what they are meant to catch."""

    def test_every_table_needs_its_own_header_cells(self) -> None:
        outline = Outline()
        outline.feed(
            '<table><tr><th scope="col">A</th><th scope="col">B</th></tr></table>'
            "<table><tr><td>no header</td></tr></table>"
        )
        self.assertEqual(outline.header_cells, [2, 0])

    def test_an_empty_aria_label_is_no_label(self) -> None:
        outline = Outline()
        outline.feed('<input type="text" aria-label=""><input type="text" aria-label="Name">')
        self.assertEqual(outline.fields, ["", None])
