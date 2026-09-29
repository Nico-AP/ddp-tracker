"""Suggesting and deciding (proposals/services.py): staff apply directly, everyone else
proposes; accepting applies and supersedes, rejecting records why."""

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import (
    ProposalError,
    StaleError,
    accept,
    changes,
    is_stale,
    reject,
    submit,
    withdraw,
)
from ddp_tracker.representations.models import (
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.services import create_annotation
from ddp_tracker.users.models import User

Kind, Status = Proposal.Kind, Proposal.Status
DATA = {"a.json": b'{"name": "Anna", "email": "a@b.c", "videos": [{"when": "2024-01-01"}]}'}


class ProposalTestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", is_staff=True)
        self.curator = User.objects.create_user("curator")
        self.other = User.objects.create_user("other")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(self.platform, DATA, register=True)
        self.name = Location.objects.get(path="/a.json/name")
        self.email = Location.objects.get(path="/a.json/email")
        self.shown = create_annotation(self.email, "Email", self.staff)


class SubmitTests(ProposalTestCase):
    def test_staff_apply_directly(self):
        self.assertIsNone(submit(self.staff, Kind.LINK, location=self.name, annotation=self.shown))
        self.name.refresh_from_db()
        self.assertEqual(self.name.annotation, self.shown)
        self.assertFalse(Proposal.objects.exists())

    def test_others_propose_and_nothing_changes(self):
        proposal = submit(
            self.curator,
            Kind.NEW_ANNOTATION,
            location=self.name,
            values={"name": "Display name", "description": "Shown"},
            comment=" the profile's name ",
        )
        assert proposal is not None
        self.name.refresh_from_db()
        self.assertIsNone(self.name.annotation)
        self.assertFalse(Annotation.objects.filter(name="Display name").exists())
        self.assertEqual(
            (proposal.status, proposal.platform, proposal.comment),
            (Status.OPEN, self.platform, "the profile's name"),
        )
        self.assertEqual(proposal.base, {"annotation": None, "ignored": False})
        self.assertEqual(changes(proposal)[0], ("Annotation", "none", "new: Display name"))

    def test_a_newer_suggestion_replaces_ones_own(self):
        first = submit(self.curator, Kind.IGNORE, location=self.name)
        second = submit(self.curator, Kind.LINK, location=self.name, annotation=self.shown)
        theirs = submit(self.other, Kind.IGNORE, location=self.name)
        assert first is not None
        assert second is not None
        assert theirs is not None
        first.refresh_from_db()
        self.assertEqual(first.status, Status.WITHDRAWN)
        self.assertEqual(
            set(Proposal.objects.filter(status=Status.OPEN).values_list("pk", flat=True)),
            {second.pk, theirs.pk},  # others' suggestions stay: alternatives
        )

    def test_invalid_changes_are_refused(self):
        other_platform = Platform.objects.create(name="YouTube", slug="youtube")
        foreign = Annotation.objects.create(platform=other_platform, name="Foreign")
        with self.assertRaisesMessage(ProposalError, "another platform"):
            submit(self.curator, Kind.LINK, location=self.name, annotation=foreign)
        with self.assertRaisesMessage(ProposalError, "needs a data point"):
            submit(self.curator, Kind.IGNORE)
        with self.assertRaisesMessage(ProposalError, "name"):
            submit(self.curator, Kind.NEW_ANNOTATION, location=self.name, values={"name": ""})


class DecideTests(ProposalTestCase):
    def test_accept_applies_and_supersedes_the_rest(self):
        mine = submit(self.curator, Kind.LINK, location=self.name, annotation=self.shown)
        theirs = submit(self.other, Kind.IGNORE, location=self.name)
        assert mine is not None
        assert theirs is not None
        with self.assertRaises(PermissionDenied):
            accept(mine, self.curator)
        accept(mine, self.staff)
        self.name.refresh_from_db()
        self.assertEqual(self.name.annotation, self.shown)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual((mine.status, mine.decided_by), (Status.ACCEPTED, self.staff))
        self.assertEqual(theirs.status, Status.SUPERSEDED)
        self.assertIn("Another suggestion", theirs.reason)
        with self.assertRaisesMessage(ProposalError, "decided already"):
            accept(mine, self.staff)

    def test_a_new_annotation_is_the_proposers(self):
        proposal = submit(
            self.curator,
            Kind.NEW_ANNOTATION,
            location=self.name,
            values={"name": "Display name", "note": "n", "pii": True},
        )
        assert proposal is not None
        self.assertIn(("PII", "", "yes"), changes(proposal))
        accept(proposal, self.staff)
        created = Annotation.objects.get(name="Display name")
        self.assertEqual((created.note, created.updated_by), ("n", self.curator))
        self.assertTrue(created.pii)
        self.assertEqual(Location.objects.get(pk=self.name.pk).annotation, created)

    def test_stale_proposals_need_confirming(self):
        proposal = submit(self.curator, Kind.LINK, location=self.name, annotation=self.shown)
        assert proposal is not None
        create_annotation(self.name, "Changed meanwhile", self.staff)
        with self.assertRaises(StaleError):
            accept(proposal, self.staff)
        accept(proposal, self.staff, stale_ok=True)
        self.assertEqual(Location.objects.get(pk=self.name.pk).annotation, self.shown)

    def test_reject_and_withdraw(self):
        proposal = submit(self.curator, Kind.IGNORE, location=self.name)
        other = submit(self.other, Kind.IGNORE, location=self.name)
        assert proposal is not None
        assert other is not None
        reject(proposal, self.staff, " not true ")
        proposal.refresh_from_db()
        self.assertEqual((proposal.status, proposal.reason), (Status.REJECTED, "not true"))
        with self.assertRaises(PermissionDenied):
            withdraw(other, self.curator)  # not theirs
        withdraw(other, self.other)
        other.refresh_from_db()
        self.assertEqual(other.status, Status.WITHDRAWN)
        with self.assertRaises(PermissionDenied):
            reject(other, self.curator, "no")

    def test_each_location_kind(self):
        for kind, expected in ((Kind.IGNORE, (None, True)), (Kind.UNASSIGN, (None, False))):
            with self.subTest(kind=kind):
                proposal = submit(self.curator, kind, location=self.email)
                assert proposal is not None
                accept(proposal, self.staff, stale_ok=True)
                self.email.refresh_from_db()
                self.assertEqual((self.email.annotation, self.email.ignored), expected)

    def test_edit_annotation(self):
        values = {"name": "E-mail", "description": "The address", "note": "", "pii": True}
        proposal = submit(self.curator, Kind.EDIT_ANNOTATION, annotation=self.shown, values=values)
        assert proposal is not None
        self.assertIn(("Name", "Email", "E-mail"), changes(proposal))
        self.assertIn(("PII", "no", "yes"), changes(proposal))
        accept(proposal, self.staff)
        self.shown.refresh_from_db()
        self.assertEqual((self.shown.name, self.shown.updated_by), ("E-mail", self.curator))
        self.assertTrue(self.shown.pii)


class RepresentationTests(ProposalTestCase):
    def setUp(self):
        super().setUp()
        self.video = ObjectType.objects.get(slug="video")
        self.item = Location.objects.get(path="/a.json/videos/[]")  # not annotated: no matter
        self.when = Location.objects.get(path="/a.json/videos/[]/when")
        self.values = {"pattern": Pattern.OBJECT, "name": "Video", "object": self.video.pk}

    def test_new_representation_of_a_location(self):
        with self.assertRaisesMessage(ProposalError, "needs a data point"):
            submit(self.curator, Kind.NEW_REPRESENTATION, values=self.values)
        with self.assertRaisesMessage(ProposalError, "can't have representations"):
            submit(self.curator, Kind.NEW_REPRESENTATION, location=self.name, values=self.values)
        proposal = submit(
            self.curator, Kind.NEW_REPRESENTATION, location=self.item, values=self.values
        )
        assert proposal is not None
        self.assertFalse(Representation.objects.exists())
        self.assertEqual(proposal.platform, self.platform)
        rows = [(f, b, a.lower()) for f, b, a in changes(proposal)]
        self.assertIn(("Object", "", "video"), rows)
        self.assertIn(("Of", "", self.item.path), rows)
        accept(proposal, self.staff)
        created = Representation.objects.get(name="Video")
        self.assertEqual(created.location, self.item)
        proposal.refresh_from_db()
        self.assertEqual(proposal.representation, created)

    def test_new_representation_with_metadata_rows(self):
        when = MetadataRole.objects.get(slug="when")
        row = {"subject": "object", "role": when.pk, "location": self.when.pk}
        refused = [
            (row | {"subject": "actor"}, "describe the actor"),  # no actor
            (row | {"location": self.name.pk}, "metadata row"),  # not below the item
        ]
        for bad, message in refused:
            with self.subTest(row=bad), self.assertRaisesMessage(ProposalError, message):
                submit(
                    self.curator,
                    Kind.NEW_REPRESENTATION,
                    location=self.item,
                    values=self.values | {"metadata": [bad]},
                )
        proposal = submit(
            self.curator,
            Kind.NEW_REPRESENTATION,
            location=self.item,
            values=self.values | {"metadata": [row]},
        )
        assert proposal is not None
        self.assertIn(("Metadata", "", f"{self.when.path}: when of the object"), changes(proposal))
        accept(proposal, self.staff)
        created = Representation.objects.get(name="Video")
        self.assertEqual(
            list(created.metadata_links.values_list("location", "role", "subject")),
            [(self.when.pk, when.pk, "object")],
        )

    def test_edit_replaces_the_metadata_and_deletion(self):
        video = Representation.objects.create(
            location=self.item, pattern=Pattern.OBJECT, name="Video", object=self.video
        )
        when = MetadataRole.objects.get(slug="when")
        row = {"subject": "object", "role": when.pk, "location": self.when.pk}
        with self.assertRaisesMessage(ProposalError, "metadata row"):  # not below the item
            submit(
                self.curator,
                Kind.EDIT_REPRESENTATION,
                representation=video,
                values=self.values | {"metadata": [row | {"location": self.name.pk}]},
            )
        edit = submit(
            self.curator,
            Kind.EDIT_REPRESENTATION,
            representation=video,
            values=self.values | {"metadata": [row]},
        )
        assert edit is not None
        self.assertEqual(edit.platform, self.platform)
        self.assertEqual(edit.base["metadata"], [])
        self.assertEqual(changes(edit), [("Metadata", "", f"{self.when.path}: when of the object")])
        accept(edit, self.staff)
        self.assertEqual(RepresentationMetadata.objects.get().location, self.when)
        # the links changed since: a stale suggestion
        remove = submit(
            self.curator,
            Kind.EDIT_REPRESENTATION,
            representation=video,
            values=self.values | {"metadata": []},
        )
        assert remove is not None
        self.assertFalse(is_stale(remove))
        self.assertEqual(
            changes(remove), [("Metadata", f"{self.when.path}: when of the object", "none")]
        )
        RepresentationMetadata.objects.all().delete()
        self.assertTrue(is_stale(remove))
        # without metadata in the values: the links stay
        RepresentationMetadata.objects.create(
            representation=video, location=self.when, role=when, subject="object"
        )
        rename = submit(
            self.curator,
            Kind.EDIT_REPRESENTATION,
            representation=video,
            values=self.values | {"name": "Clip"},
        )
        assert rename is not None
        accept(rename, self.staff)
        self.assertTrue(RepresentationMetadata.objects.exists())
        delete = submit(self.curator, Kind.DELETE_REPRESENTATION, representation=video)
        assert delete is not None
        self.assertFalse(is_stale(delete))
        accept(delete, self.staff)
        self.assertFalse(Representation.objects.exists())
        delete.refresh_from_db()
        self.assertEqual(changes(delete), [("Representation", "Clip", "none")])

    def test_unapproved_vocabulary_waits(self):
        mine = ObjectType.objects.create(name="Clip", created_by=self.curator)  # suggested only
        pending = submit(
            self.curator,
            Kind.NEW_REPRESENTATION,
            location=self.item,
            values={"pattern": Pattern.OBJECT, "name": "Clips", "object": mine.pk},
        )
        assert pending is not None
        with self.assertRaisesMessage(ProposalError, "object"):
            accept(pending, self.staff)  # "Clip" isn't approved yet
        mine.approved = True
        mine.save()
        accept(pending, self.staff)
        self.assertTrue(Representation.objects.filter(name="Clips").exists())
