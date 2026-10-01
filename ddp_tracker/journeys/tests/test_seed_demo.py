"""``manage.py seed_demo``: an empty database becomes a demo, through the site's own code."""

import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from allauth.account.models import EmailAddress

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform, Upload
from ddp_tracker.journeys.demo.spec import (
    ADMIN_EMAIL,
    ANNOTATIONS,
    CURATOR_EMAIL,
    EXAMPLES,
    REPRESENTATIONS,
    SUGGESTION_PATH,
    ExampleSpec,
)
from ddp_tracker.journeys.tests.utils import SeededTestCase, seed_demo
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.templatetags.proposal_tags import proposals_waiting
from ddp_tracker.representations.models import ActivityType, Representation
from ddp_tracker.reviews.services import NEW, review, scopes
from ddp_tracker.schemas.examples import USER_INPUT
from ddp_tracker.schemas.models import Location, Observation
from ddp_tracker.users.models import User

T = "/user_data_tiktok.json"
MODELS = (User, Platform, Upload, Location, Observation, Annotation, Representation, Proposal)


VARIABLE = "DJANGO_DEMO_PASSWORD"


def counts():
    return {model.__name__: model.objects.count() for model in MODELS}


@contextmanager
def demo_password(value: str | None) -> Iterator[None]:
    """``DJANGO_DEMO_PASSWORD`` set to ``value``, or not set at all (``None``)."""
    with mock.patch.dict(os.environ):
        os.environ.pop(VARIABLE, None)
        if value is not None:
            os.environ[VARIABLE] = value
        yield


def printed_password(output: str) -> str:
    found = re.search(r"Password for both: (\S+)", output)
    assert found, output
    return found.group(1)


class DemoDataTests(SeededTestCase):
    """What the demo data is (seeded once for the class)."""

    def test_users(self):
        admin = User.objects.get(email=ADMIN_EMAIL)
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertFalse(User.objects.get(email=CURATOR_EMAIL).is_staff)
        # accounts sign in with a verified address
        self.assertEqual(EmailAddress.objects.filter(verified=True, primary=True).count(), 2)

    def test_platforms_and_uploads(self):
        self.assertEqual(
            set(Platform.objects.values_list("slug", flat=True)),
            {"facebook", "instagram", "tiktok", "youtube"},
        )
        registered = Upload.objects.filter(registered_at__isnull=False)
        self.assertEqual(
            sorted(registered.values_list("platform__slug", "requested_at")),
            [
                ("facebook", date(2026, 9, 15)),
                ("instagram", date(2026, 9, 15)),
                ("tiktok", date(2026, 3, 15)),
                ("tiktok", date(2026, 9, 15)),
            ],
        )
        # stored as any upload is: the name anonymised, the structure only
        self.assertTrue(all(upload.document for upload in registered))
        self.assertNotIn("noor", " ".join(registered.values_list("file_name", flat=True)))

    def test_one_upload_waits_for_approval(self):
        held = Upload.objects.get(platform__slug="youtube")
        self.assertEqual(held.plausibility, Upload.Plausibility.AWAITING)
        self.assertEqual(held.plausibility_reason, Upload.Reason.FIRST)
        self.assertIsNone(held.registered_at)
        self.assertEqual(held.uploaded_by, User.objects.get(email=CURATOR_EMAIL))

    def test_the_september_tiktok_upload_has_something_to_show(self):
        september = Upload.objects.get(platform__slug="tiktok", requested_at=date(2026, 9, 15))
        self.assertEqual(september.plausibility, Upload.Plausibility.PASSED)  # by itself
        new = set(
            Location.objects.filter(pk__in=scopes(september)[NEW]).values_list("path", flat=True)
        )
        self.assertIn(f"{T}/Tiktok Live/Go Live History/GoLiveList", new)
        watch = f"{T}/Your Activity/Watch History/VideoList/[]"
        self.assertIn(watch, new)
        # recognised as the older section's list, moved
        moved = september.observations.get(location__path=watch).suggestions[0]
        self.assertEqual(moved["path"], f"{T}/Activity/Video Browsing History/VideoList/[]")
        found = review(september)
        self.assertEqual(
            {item.observation.location.path: item.fields for item in found.changed},
            {f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date": ["format"]},
        )
        self.assertEqual(
            [item.location.path for item in found.missing],
            [f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived"],
        )

    def test_annotations(self):
        self.assertEqual(Annotation.objects.count(), len(ANNOTATIONS))
        for spec in ANNOTATIONS:
            with self.subTest(annotation=f"{spec.platform}: {spec.name}"):
                annotation = Annotation.objects.get(platform__slug=spec.platform, name=spec.name)
                self.assertEqual(annotation.pii, spec.pii)
                self.assertEqual(
                    set(annotation.locations.values_list("path", flat=True)), set(spec.paths)
                )
        # one data point at two paths: the old section name and the new one
        watched = Annotation.objects.get(platform__slug="tiktok", name="Watched video")
        self.assertEqual(watched.locations.count(), 2)

    def test_representations(self):
        self.assertEqual(Representation.objects.count(), len(REPRESENTATIONS))
        watched = Representation.objects.get(
            location__platform__slug="tiktok", name="Watched a video"
        )
        self.assertEqual(watched.statement, "user · viewed · video")
        self.assertEqual(
            {
                (link.relative_path, link.role.slug, link.subject)
                for link in watched.metadata_links.all()
            },
            {("Date", "when", "activity"), ("Link", "identifier", "object")},
        )
        # public representations only use approved terms
        self.assertFalse(Representation.objects.filter(activity__approved=False).exists())

    def test_example_values_are_a_curators(self):
        for spec in EXAMPLES:
            location = Location.objects.get(platform__slug=spec.platform, path=spec.path)
            self.assertEqual(
                location.example_values,
                [{"value": value, "source": USER_INPUT} for value in spec.examples],
            )

    def test_the_queues_are_not_empty(self):
        self.assertEqual(proposals_waiting()["annotations"], 1)
        suggestion = Proposal.objects.get()
        self.assertEqual(
            suggestion.location, Location.objects.get(platform__slug="tiktok", path=SUGGESTION_PATH)
        )
        self.assertEqual(suggestion.proposed_by, User.objects.get(email=CURATOR_EMAIL))
        self.assertTrue(suggestion.is_open)
        liked = ActivityType.objects.get(slug="liked")
        self.assertFalse(liked.approved)  # waits for an administrator


class SeedDemoCommandTests(TestCase):
    def test_refuses_to_run_without_debug(self):
        with self.assertRaisesMessage(CommandError, "DEBUG is off"):
            call_command("seed_demo")
        self.assertFalse(Platform.objects.exists())

    def test_says_what_it_created_and_how_to_log_in(self):
        output = seed_demo()  # the helper also checks that no package file is left behind
        self.assertIn("Created: 2 users, 4 platforms, 5 uploads, 28 annotations", output)
        self.assertIn("1 suggested term, 1 suggestion.", output)  # one of a kind: singular
        self.assertIn(ADMIN_EMAIL, output)
        self.assertIn("Password", output)

    def test_a_path_that_does_not_exist_stops_it_and_changes_nothing(self):
        wrong = (ExampleSpec("tiktok", "/no/such/path", ("x",)),)
        with (
            mock.patch("ddp_tracker.journeys.demo.seed.EXAMPLES", wrong),
            tempfile.TemporaryDirectory() as incoming,
            override_settings(DDP_INCOMING_DIR=incoming),
        ):
            with self.assertRaisesMessage(CommandError, "/no/such/path"):
                call_command("seed_demo", force=True)
            self.assertEqual(list(Path(incoming).iterdir()), [])  # no package file kept
        self.assertFalse(Platform.objects.exists())  # all of it rolled back

    def test_running_it_again_creates_nothing(self):
        seed_demo()
        before = counts()
        output = seed_demo()
        self.assertEqual(counts(), before)
        self.assertIn("Created: nothing.", output)
        self.assertIn("exist already", output)

    def test_it_leaves_what_a_person_changed(self):
        seed_demo()
        annotation = Annotation.objects.get(platform__slug="tiktok", name="Search term")
        annotation.name = "Search text"
        annotation.save()
        before = counts()
        seed_demo()
        self.assertEqual(counts(), before)
        self.assertFalse(Annotation.objects.filter(platform__slug="tiktok", name="Search term"))

    def test_refuses_without_debug_although_a_password_is_set(self):
        with (
            demo_password("test-only-password"),
            self.assertRaisesMessage(CommandError, "DEBUG is off"),
        ):
            call_command("seed_demo")
        self.assertFalse(Platform.objects.exists())

    def test_the_password_from_the_environment_is_used_for_both_users(self):
        with demo_password("test-only-password"):
            output = seed_demo()
        for email in (ADMIN_EMAIL, CURATOR_EMAIL):
            self.assertTrue(User.objects.get(email=email).check_password("test-only-password"))
        self.assertEqual(printed_password(output), "test-only-password")
        self.assertIn(f"from {VARIABLE}", output)

    @override_settings(DEBUG=True)
    def test_with_debug_it_runs_unforced_and_uses_the_password_from_the_environment(self):
        with demo_password("test-only-password"):
            seed_demo(force=False)  # no need to force it: DEBUG is on
        self.assertTrue(User.objects.get(email=CURATOR_EMAIL).check_password("test-only-password"))

    def test_without_the_variable_the_password_is_random(self):
        passwords = []
        for _ in range(2):  # two fresh runs
            with demo_password(None):
                output = seed_demo()
            password = printed_password(output)
            for email in (ADMIN_EMAIL, CURATOR_EMAIL):
                self.assertTrue(User.objects.get(email=email).check_password(password))
            self.assertIn(f"made up at random; set {VARIABLE} to choose your own", output)
            self.assertEqual(output.count(password), 1)  # printed once
            passwords.append(password)
            seed_demo(reset=True)
        self.assertNotEqual(passwords[0], passwords[1])

    def test_an_empty_variable_counts_as_not_set(self):
        with demo_password(""):
            output = seed_demo()
        password = printed_password(output)
        self.assertTrue(password)
        self.assertTrue(User.objects.get(email=ADMIN_EMAIL).check_password(password))
        self.assertIn("made up at random", output)

    def test_reset_removes_the_demo_data(self):
        terms = ActivityType.objects.count()
        seed_demo()
        output = seed_demo(reset=True)
        self.assertEqual(set(counts().values()), {0})
        self.assertEqual(ActivityType.objects.count(), terms)  # the vocabulary is as before
        self.assertIn("Removed:", output)

    def test_reset_keeps_a_platform_that_others_uploaded_to(self):
        seed_demo()
        tiktok = Platform.objects.get(slug="tiktok")
        someone = User.objects.create_user("someone@example.org")
        theirs = parsed_upload(tiktok, {"a.json": b'{"x": 1}'}, register=True, user=someone)
        seed_demo(reset=True)
        self.assertEqual(list(Upload.objects.all()), [theirs])
        self.assertEqual(list(Platform.objects.values_list("slug", flat=True)), ["tiktok"])
        self.assertFalse(Annotation.objects.exists())
