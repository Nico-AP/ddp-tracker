"""The journeys as data (content.py): complete, well formed, and every link leads somewhere."""

from urllib.parse import urlsplit

from django.test import SimpleTestCase
from django.urls import resolve

from ddp_tracker.journeys.content import (
    AVAILABLE,
    FEATURE_STATUSES,
    NEEDS,
    PROTOTYPE,
    ROLES,
    ROLES_BY_SLUG,
    STATUSES,
)
from ddp_tracker.journeys.targets import DEMO_LINK_KEYS


class ContentTests(SimpleTestCase):
    def test_the_eight_roles_in_order(self):
        self.assertEqual(
            [role.slug for role in ROLES],
            [
                "researcher",
                "engineer",
                "policy",
                "contributor",
                "curator",
                "admin",
                "machine",
                "learner",
            ],
        )
        self.assertEqual(set(ROLES_BY_SLUG), {role.slug for role in ROLES})

    def test_a_journey_has_three_to_five_steps(self):
        for role in ROLES:
            with self.subTest(role=role.slug):
                self.assertGreaterEqual(len(role.steps), 3)
                self.assertLessEqual(len(role.steps), 5)
                self.assertEqual(role.available_count + role.prototype_count, len(role.steps))

    def test_steps_are_well_formed(self):
        for role in ROLES:
            for step in role.steps:
                with self.subTest(role=role.slug, step=step.title):
                    self.assertIn(step.status, STATUSES)
                    self.assertIn(step.needs, NEEDS)
                    self.assertIn(step.demo_link, ("", *DEMO_LINK_KEYS))
                    self.assertTrue(step.title and step.text and step.link_label)
                    # a prototype step leads to a mock-up, an available one to a page that exists
                    is_mockup = step.url_name.startswith("journeys:")
                    self.assertEqual(is_mockup, step.status == PROTOTYPE)
                    # a "today" link comes with its label, and only on prototype steps
                    self.assertEqual(bool(step.today_url_name), bool(step.today_label))
                    if step.today_url_name:
                        self.assertEqual(step.status, PROTOTYPE)

    def test_every_link_leads_somewhere(self):
        for role in ROLES:
            for step in role.steps:
                with self.subTest(role=role.slug, step=step.title):
                    resolve(urlsplit(step.url).path)  # raises Resolver404 if nothing is there
                    if step.today_url:
                        resolve(urlsplit(step.today_url).path)

    def test_link_texts_make_sense_out_of_context(self):
        for role in ROLES:
            labels = [step.link_label for step in role.steps]
            with self.subTest(role=role.slug):
                self.assertEqual(len(labels), len(set(labels)))  # no two links read the same
                for label in labels:
                    self.assertGreater(len(label.split()), 2, label)  # not "Go" or "Open it"

    def test_both_kinds_of_step_occur(self):
        statuses = {step.status for role in ROLES for step in role.steps}
        self.assertEqual(statuses, {AVAILABLE, PROTOTYPE})

    def test_features_have_a_known_status(self):
        for role in ROLES:
            self.assertTrue(role.features, role.slug)
            for feature in role.features:
                self.assertIn(feature.status, FEATURE_STATUSES)

    def test_the_texts_have_no_em_dash(self):
        for role in ROLES:
            for thing in (role, *role.steps, *role.features):
                for name, value in vars(thing).items():
                    if isinstance(value, str):
                        self.assertNotIn("\u2014", value, f"{role.slug}: {name}")
