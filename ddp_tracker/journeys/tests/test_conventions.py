"""Rules that production enforces and local development does not (the content security policy
allows no inline style or script), and the project's writing rules: checked on this app's
templates and sources, so that a slip shows up in the tests and not on the live site."""

import re
from pathlib import Path

from django.test import SimpleTestCase

APP = Path(__file__).resolve().parent.parent
TEMPLATES = sorted((APP / "templates").rglob("*.html"))
SOURCES = sorted(APP.rglob("*.py"))
EM_DASH = "\u2014"
SIZES = {"btn-sm", "btn-lg"}


def templates():
    return [(path.name, path.read_text(encoding="utf-8")) for path in TEMPLATES]


class ConventionsTests(SimpleTestCase):
    def test_there_are_templates_to_check(self):
        self.assertTrue(TEMPLATES)

    def test_no_inline_styles(self):
        for name, text in templates():
            with self.subTest(template=name):
                self.assertNotRegex(text, r"\sstyle\s*=")
                self.assertNotIn("<style", text)

    def test_scripts_are_files(self):
        for name, text in templates():
            with self.subTest(template=name):
                for tag in re.findall(r"<script\b[^>]*>", text):
                    self.assertIn("src=", tag)

    def test_no_inline_event_handlers(self):
        for name, text in templates():
            with self.subTest(template=name):
                self.assertNotRegex(text, r"\son[a-z]+\s*=\s*[\"']")

    def test_buttons_name_a_variant(self):
        for name, text in templates():
            with self.subTest(template=name):
                for classes in re.findall(r'class="([^"]*)"', text):
                    names = classes.split()
                    if "btn" in names:
                        variants = [n for n in names if n.startswith("btn-") and n not in SIZES]
                        self.assertTrue(variants, classes)

    def test_no_user_e_mail_addresses(self):
        for name, text in templates():
            with self.subTest(template=name):
                self.assertNotIn(".email", text)

    def test_no_fictional_labels(self):
        # the prototype banner says once per page that the data is fictional
        for name, text in templates():
            with self.subTest(template=name):
                self.assertNotIn("badge--fictional", text)

    def test_no_em_dash(self):
        for path in [*TEMPLATES, *SOURCES]:
            with self.subTest(file=path.name):
                self.assertNotIn(EM_DASH, path.read_text(encoding="utf-8"))
