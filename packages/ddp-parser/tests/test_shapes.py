from unittest import TestCase

from ddp_parser.model import Shape
from ddp_parser.schematize.shapes import classify_number, classify_string, is_id_key


class StringShapeTests(TestCase):
    def test_spec_order(self):
        cases = {
            "": Shape.EMPTY,
            "   ": Shape.EMPTY,
            "550e8400-e29b-41d4-a716-446655440000": Shape.UUID,
            "anna@example.com": Shape.EMAIL,
            "https://example.com/a?b=1": Shape.URL,
            "ftp://host/file": Shape.URL,
            "2021-03-14T09:26:53Z": Shape.DATETIME,
            "2021-03-14": Shape.DATE,
            "09:26": Shape.TIME,
            "1767225600": Shape.UNIX_TIMESTAMP,
            "42": Shape.NUMERIC,
            "-3.14": Shape.NUMERIC,
            "1e5": Shape.NUMERIC,
            "DE": Shape.ALPHA,
            "Zürich": Shape.ALPHA,
            "abc123": Shape.ALPHANUMERIC,
            "Anna Muster": Shape.TEXT,
            "a-b": Shape.TEXT,
        }
        for value, shape in cases.items():
            with self.subTest(value=value):
                self.assertEqual(classify_string(value, id_key=False)[0], shape)

    def test_unix_digits_carry_unit(self):
        self.assertEqual(
            classify_string("1767225600000", id_key=False),
            (Shape.UNIX_TIMESTAMP, frozenset({"ms"})),
        )

    def test_id_key_suppresses_unix_timestamp(self):
        self.assertEqual(classify_string("1767225600", id_key=True)[0], Shape.NUMERIC)

    def test_very_long_digit_string_is_numeric(self):
        self.assertEqual(classify_string("9" * 5000, id_key=False)[0], Shape.NUMERIC)


class NumberShapeTests(TestCase):
    def test_unix_ranges(self):
        cases = [
            (631_152_000, "s"),  # 1990-01-01
            (4_102_444_799, "s"),  # last second before 2100
            (1_767_225_600_000, "ms"),
            (1_767_225_600_000_000, "us"),
            (1_767_225_600.5, "s"),
        ]
        for value, unit in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    classify_number(value, id_key=False),
                    (Shape.UNIX_TIMESTAMP, frozenset({unit})),
                )

    def test_out_of_range_is_plain(self):
        for value in [0, 42, 631_151_999, 4_102_444_800, 99_999_999_999]:
            with self.subTest(value=value):
                self.assertEqual(classify_number(value, id_key=False)[0], Shape.PLAIN)

    def test_id_key_suppresses(self):
        self.assertEqual(classify_number(1_767_225_600, id_key=True)[0], Shape.PLAIN)


class IdKeyTests(TestCase):
    def test_id_keys(self):
        for name in ["id", "ID", "user_id", "USER_ID", "userId", "thread2Id"]:
            with self.subTest(name=name):
                self.assertTrue(is_id_key(name))

    def test_not_id_keys(self):
        for name in [None, "video", "valid", "ideas", "identity", "paid", "timestamp"]:
            with self.subTest(name=name):
                self.assertFalse(is_id_key(name))
