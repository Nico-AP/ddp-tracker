"""The definitions of "new" and "changed" (docs/docs/tracker/concepts.md)."""

from datetime import date

from django.test import TestCase

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.schemas.profiles import profiles
from ddp_tracker.schemas.timeline import changes_in, new_in, normalized


def export(value: str) -> dict[str, bytes]:
    return {"a.json": f'{{"when": "{value}"}}'.encode()}


class TimelineTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="X", slug="x")

    def upload(self, requested_at: date, members: dict[str, bytes]):
        return parsed_upload(self.platform, members, requested_at=requested_at, register=True)

    def when(self):
        return Location.objects.get(path="/a.json/when").pk

    def test_the_documented_example(self):
        # registered out of order on purpose: only request dates count
        u2026_05 = self.upload(date(2026, 5, 1), export("2026-01-01"))
        u2026_02 = self.upload(date(2026, 2, 1), export("01.02.2026"))
        u2025_03 = self.upload(date(2025, 3, 1), export("2025-01-01"))
        u2025_09 = self.upload(date(2025, 9, 1), export("2025-02-02"))
        u2026_07 = self.upload(date(2026, 7, 1), export("03.04.2026"))
        when = self.when()
        self.assertEqual(changes_in(u2025_03), {})  # the first export: everything is new
        self.assertIn(when, new_in(u2025_03))
        self.assertEqual(changes_in(u2025_09), {})
        self.assertEqual(changes_in(u2026_02), {when: ["format"]})  # %d.%m.%Y appears
        self.assertEqual(changes_in(u2026_05), {})  # %Y-%m-%d was seen before
        self.assertEqual(changes_in(u2026_07), {})  # %d.%m.%Y was seen before
        self.assertNotIn(when, new_in(u2026_05))

    def test_same_request_date_is_not_earlier(self):
        first = self.upload(date(2026, 1, 1), export("2026-01-01"))
        second = self.upload(date(2026, 1, 1), export("01.01.2026"))
        self.assertEqual((changes_in(first), changes_in(second)), ({}, {}))
        self.assertIn(self.when(), new_in(second))

    def test_noise_is_ignored(self):
        self.upload(date(2025, 1, 1), {"a.json": b'{"x": "abc", "y": ["a b", "c"]}'})
        later = self.upload(
            date(2026, 1, 1), {"a.json": b'{"x": null, "y": ["a b", "cd ef", "g"]}'}
        )
        # x: only null now (type "null" is ignored); y: alpha/text mix → "mixed" is ignored
        self.assertEqual(changes_in(later), {})

    def test_type_and_kind_changes(self):
        self.upload(date(2025, 1, 1), {"a.json": b'{"n": 1}'})
        later = self.upload(date(2026, 1, 1), {"a.json": b'{"n": "one"}'})
        n = Location.objects.get(path="/a.json/n").pk
        self.assertEqual(changes_in(later)[n], ["type", "shape"])
        broken = self.upload(date(2026, 6, 1), {"a.json": b"{"})
        self.assertEqual(changes_in(broken)[Location.objects.get(path="/a.json").pk], ["kind"])

    def test_normalized(self):
        self.assertEqual(normalized("type", "string|null"), "string")
        self.assertEqual(normalized("type", "null"), "")
        self.assertEqual(normalized("shape", "mixed"), "")
        self.assertEqual(normalized("format", "%Y"), "%Y")


class ProfileTests(TestCase):
    def test_data_points(self):
        platform = Platform.objects.create(name="X", slug="x")
        members = {"a.json": b'{"e": [], "d": {"x": 1}, "rows": [{"k": 1}]}'}
        parsed_upload(platform, members, register=True)
        parsed_upload(platform, {"a.json": b'{"e": "x", "d": {"x": 2}, "rows": []}'}, register=True)
        locations = {loc.path: loc.pk for loc in Location.objects.all()}
        found = profiles(locations.values(), Observation.objects.all())
        e = found[locations["/a.json/e"]]
        self.assertEqual(e.types, {"array": 1, "string": 1})
        self.assertEqual((e.main_kind, e.uploads), ("data", 2))
        expected = {
            "/a.json/e": True,  # a list, then a value
            "/a.json/d/x": True,  # a value
            "/a.json/rows": True,  # a list
            "/a.json/rows/[]": True,  # the repeated entity: an object item of a list
            "/a.json/d": False,  # an object that only groups keys
            "/a.json": False,  # a parsed file
            "": False,  # the root
        }
        for path, is_data_point in expected.items():
            with self.subTest(path=path):
                self.assertEqual(found[locations[path]].is_data_point, is_data_point)

    def test_empty_profile(self):
        found = profiles([999], Observation.objects.all())[999]
        self.assertEqual(
            (found.main_type, found.uploads, found.variants, found.is_data_point), ("", 0, 0, False)
        )
