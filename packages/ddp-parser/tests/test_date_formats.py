from collections import Counter
from datetime import datetime
from unittest import TestCase

from ddp_parser.model import Shape
from ddp_parser.schematize.date_formats import match_formats, resolve_format, to_strptime


class MatchFormatsTests(TestCase):
    def test_formats(self):
        cases = {
            "2021-03-14T09:26:53Z": (Shape.DATETIME, "%Y-%m-%dT%H:%M:%SZ"),
            "2026-08-01 10:12:04": (Shape.DATETIME, "%Y-%m-%d %H:%M:%S"),
            "2024-01-01T10:00:00+02:00": (Shape.DATETIME, "%Y-%m-%dT%H:%M:%S%z"),
            "Mon, 10 Jan 2024 10:00:00 +0000": (Shape.DATETIME, "%a, %d %b %Y %H:%M:%S %z"),
            "Jan 10, 2024 3:04 PM": (Shape.DATETIME, "%b %d, %Y %I:%M %p"),
            "14.03.2021": (Shape.DATE, "%d.%m.%Y"),
            "10 May 2024": (Shape.DATE, "%d %b %Y"),
            "10 June 2024": (Shape.DATE, "%d %B %Y"),
            "23:59:59": (Shape.TIME, "%H:%M:%S"),
        }
        for value, (shape, fmt) in cases.items():
            with self.subTest(value=value):
                self.assertEqual(match_formats(value), (shape, frozenset({fmt})))

    def test_fraction_digits_are_part_of_the_format(self):
        self.assertEqual(
            match_formats("2024-01-01T10:00:00.123Z"),
            (Shape.DATETIME, frozenset({"%Y-%m-%dT%H:%M:%S.%3fZ"})),
        )
        self.assertEqual(to_strptime("%Y-%m-%dT%H:%M:%S.%3fZ"), "%Y-%m-%dT%H:%M:%S.%fZ")
        datetime.strptime("2024-01-01T10:00:00.123Z", to_strptime("%Y-%m-%dT%H:%M:%S.%3fZ"))  # noqa: DTZ007

    def test_ambiguous_day_month_order_returns_both(self):
        self.assertEqual(
            match_formats("01/02/2026"), (Shape.DATE, frozenset({"%d/%m/%Y", "%m/%d/%Y"}))
        )

    def test_same_structure_different_validity(self):
        # Shares a cached signature with 01/02/2026, but only one order is a valid date.
        match_formats("01/02/2026")
        self.assertEqual(match_formats("13/02/2026"), (Shape.DATE, frozenset({"%d/%m/%Y"})))
        self.assertEqual(match_formats("02/13/2026"), (Shape.DATE, frozenset({"%m/%d/%Y"})))

    def test_not_dates(self):
        for value in [
            "2024",
            "hello",
            "99/99/2026",
            "Meet at 10:00 tomorrow",
            "1.2.3",
            "2024-13-01",
            "x" * 50,
        ]:
            with self.subTest(value=value):
                self.assertIsNone(match_formats(value))


class ResolveFormatTests(TestCase):
    def test_single_common_format(self):
        fits = Counter({frozenset({"%d/%m/%Y", "%m/%d/%Y"}): 3, frozenset({"%d/%m/%Y"}): 1})
        self.assertEqual(resolve_format(fits), ("%d/%m/%Y", None, False))

    def test_ambiguous(self):
        fits = Counter({frozenset({"%d/%m/%Y", "%m/%d/%Y"}): 4})
        self.assertEqual(resolve_format(fits), (None, {"%d/%m/%Y": 4, "%m/%d/%Y": 4}, True))

    def test_different_formats_are_counted(self):
        fits = Counter({frozenset({"%Y-%m-%d"}): 2, frozenset({"%d.%m.%Y"}): 1})
        self.assertEqual(resolve_format(fits), (None, {"%Y-%m-%d": 2, "%d.%m.%Y": 1}, False))

    def test_nothing_to_resolve(self):
        self.assertEqual(resolve_format(None), (None, None, False))
        self.assertEqual(resolve_format(Counter()), (None, None, False))
