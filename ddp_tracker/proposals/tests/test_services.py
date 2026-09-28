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
        self.item = create_annotation(
            Location.objects.get(path="/a.json/videos/[]"), "Video", self.staff
        )
        self.when = create_annotation(
            Location.objects.get(path="/a.json/videos/[]/when"), "When", self.staff
        )
        self.values = {"pattern": Pattern.OBJECT, "name": "Video", "object": self.video.pk}

    def test_new_representation_with_its_entity(self):
        proposal = submit(
            self.curator,
            Kind.NEW_REPRESENTATION,
            annotation=self.item,
            values=self.values | {"relation": "represents"},
        )
        assert proposal is not None
        self.assertFalse(Representation.objects.exists())
        self.assertIn(("Object", "", "video"), [(f, b, a.lower()) for f, b, a in changes(proposal)])
        accept(proposal, self.staff)
        created = Representation.objects.get(name="Video")
        self.assertEqual(list(created.annotations.all()), [self.item])
        proposal.refresh_from_db()
        self.assertEqual(proposal.representation, created)

    def test_new_representation_with_metadata_rows(self):
        when = MetadataRole.objects.get(slug="when")
        row = {"subject": "object", "role": when.pk, "annotation": self.when.pk}
        with self.assertRaisesMessage(ProposalError, "metadata row"):
            submit(
                self.curator,
                Kind.NEW_REPRESENTATION,
                annotation=self.item,
                values=self.values | {"metadata": [row | {"subject": "actor"}]},  # no actor
            )
        proposal = submit(
            self.curator,
            Kind.NEW_REPRESENTATION,
            annotation=self.item,
            values=self.values | {"relation": "represents", "metadata": [row]},
        )
        assert proposal is not None
        self.assertIn(("Metadata", "", "When: when of the object"), changes(proposal))
        accept(proposal, self.staff)
        created = Representation.objects.get(name="Video")
        self.assertEqual(list(created.annotations.all()), [self.item])
        self.assertEqual(
            list(created.metadata_links.values_list("annotation", "role", "subject")),
            [(self.when.pk, when.pk, "object")],
        )

    def test_links_and_their_removal(self):
        video = Representation.objects.create(
            pattern=Pattern.OBJECT, name="Video", object=self.video
        )
        when = MetadataRole.objects.get(slug="when")
        entity = submit(self.curator, Kind.REPRESENT, representation=video, annotation=self.item)
        described = submit(
            self.curator,
            Kind.DESCRIBE,
            representation=video,
            annotation=self.when,
            role=when,
            subject="object",
        )
        assert entity is not None
        assert described is not None
        accept(entity, self.staff)
        accept(described, self.staff)
        self.assertEqual(list(video.annotations.all()), [self.item])
        link = RepresentationMetadata.objects.get()
        with self.assertRaisesMessage(ProposalError, "Already linked"):
            submit(self.curator, Kind.REPRESENT, representation=video, annotation=self.item)
        remove = submit(self.curator, Kind.UNREPRESENT, representation=video, annotation=self.item)
        unlink = submit(self.curator, Kind.UNDESCRIBE, metadata=link)
        assert remove is not None
        assert unlink is not None
        accept(remove, self.staff)
        accept(unlink, self.staff)
        self.assertFalse(video.annotations.exists())
        self.assertFalse(RepresentationMetadata.objects.exists())
        unlink.refresh_from_db()  # kept as history, with what the link was
        self.assertEqual((unlink.metadata, unlink.status), (None, Status.ACCEPTED))
        self.assertIn("When", changes(unlink)[0][1])

    def test_unapproved_vocabulary_waits(self):
        mine = ObjectType.objects.create(name="Clip", created_by=self.curator)  # suggested only
        pending = submit(
            self.curator,
            Kind.NEW_REPRESENTATION,
            values={"pattern": Pattern.OBJECT, "name": "Clips", "object": mine.pk},
        )
        assert pending is not None
        with self.assertRaisesMessage(ProposalError, "object"):
            accept(pending, self.staff)  # "Clip" isn't approved yet
        mine.approved = True
        mine.save()
        accept(pending, self.staff)
        self.assertTrue(Representation.objects.filter(name="Clips").exists())
