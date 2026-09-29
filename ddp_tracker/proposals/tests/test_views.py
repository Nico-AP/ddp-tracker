"""Suggesting through the existing pages (regular users) and deciding in staff's queues."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import changes, submit
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


class SuggestingTests(TestCase):
    """Regular users' changes become suggestions; nothing curated changes."""

    def setUp(self):
        self.staff = User.objects.create_user("admin", is_staff=True)
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.upload = parsed_upload(self.platform, DATA, register=True)
        self.name = Location.objects.get(path="/a.json/name")
        self.email = Location.objects.get(path="/a.json/email")
        self.shown = create_annotation(self.email, "Email", self.staff)
        self.client.force_login(self.user)

    def test_the_triage_dialog_suggests(self):
        url = reverse("schemas:triage", args=[self.name.pk])
        dialog = self.client.get(url, {"upload": self.upload.pk})
        self.assertContains(dialog, "Suggest an annotation")
        self.assertContains(dialog, "goes to staff as a suggestion")
        self.assertContains(dialog, 'name="comment"')
        response = self.client.post(
            url, {"action": "new", "name": "Display name", "comment": "the name"}
        )
        self.assertEqual(response["HX-Trigger"], f"triaged-{self.name.pk}")  # rows reload
        self.name.refresh_from_db()
        self.assertIsNone(self.name.annotation)
        proposal = Proposal.objects.get()
        self.assertEqual(
            (proposal.kind, proposal.values["name"], proposal.comment),
            (Kind.NEW_ANNOTATION, "Display name", "the name"),
        )
        # an invalid suggestion: the dialog again, with why
        invalid = self.client.post(url, {"action": "new", "name": ""})
        self.assertContains(invalid, "message--error")
        self.assertEqual(self.client.post(url, {"action": "nonsense"}).status_code, 400)

    def test_annotation_page_edits_and_unlinks_are_suggested(self):
        edit = reverse("annotations:edit", args=[self.shown.pk])
        self.assertContains(self.client.get(edit), "Suggest a change to")
        response = self.client.post(edit, {"name": "E-mail", "description": "", "note": ""})
        self.assertContains(response, "Suggested; staff will review your change.")
        self.shown.refresh_from_db()
        self.assertEqual(self.shown.name, "Email")
        unlink = self.client.post(reverse("annotations:unlink", args=[self.email.pk]))
        self.assertContains(unlink, "Suggested")
        self.assertEqual(Location.objects.get(pk=self.email.pk).annotation, self.shown)
        self.assertEqual(
            set(Proposal.objects.values_list("kind", flat=True)),
            {Kind.EDIT_ANNOTATION, Kind.UNASSIGN},
        )
        page = self.client.get(self.shown.get_absolute_url())
        self.assertContains(page, "Open suggestions")
        self.assertContains(page, reverse("proposals:for", args=["annotation", self.shown.pk]))

    def test_representations_are_suggested(self):
        video = ObjectType.objects.get(slug="video")
        create = self.client.post(
            reverse("representations:create"),
            {"pattern": Pattern.OBJECT, "name": "Video", "object": video.pk},
        )
        self.assertRedirects(create, reverse("proposals:mine"))
        self.assertFalse(Representation.objects.exists())
        existing = Representation.objects.create(pattern=Pattern.OBJECT, name="Clip", object=video)
        edit = self.client.post(
            reverse("representations:edit", args=[existing.pk]),
            {"pattern": Pattern.OBJECT, "name": "Short clip", "object": video.pk},
        )
        self.assertContains(edit, "Suggested")
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Clip")
        self.client.post(
            reverse("representations:represent", args=[self.shown.pk]),
            {"representation": existing.pk},
        )
        self.client.post(
            reverse("representations:describe", args=[self.shown.pk]),
            {
                "representation": existing.pk,
                "role": MetadataRole.objects.get(slug="when").pk,
                "subject": "object",
            },
        )
        self.client.post(
            reverse("representations:create-linked", args=[self.shown.pk]),
            {
                "pattern": Pattern.OBJECT,
                "name": "Mail",
                "object": video.pk,
                "metadata-TOTAL_FORMS": "1",
                "metadata-INITIAL_FORMS": "0",
                "metadata-0-subject": "object",
                "metadata-0-role": MetadataRole.objects.get(slug="when").pk,
                "metadata-0-annotation": self.shown.pk,
            },
        )
        self.assertFalse(existing.annotations.exists())
        self.assertFalse(RepresentationMetadata.objects.exists())
        suggested = Proposal.objects.get(kind=Kind.NEW_REPRESENTATION, values__name="Mail")
        self.assertEqual(len(suggested.values["metadata"]), 1)
        self.assertIn("Metadata", [field for field, _, _ in changes(suggested)])
        self.assertEqual(
            sorted(Proposal.objects.values_list("kind", flat=True)),
            sorted(
                [
                    Kind.NEW_REPRESENTATION,
                    Kind.EDIT_REPRESENTATION,
                    Kind.REPRESENT,
                    Kind.DESCRIBE,
                    Kind.NEW_REPRESENTATION,
                ]
            ),
        )
        link = RepresentationMetadata.objects.create(
            representation=existing,
            annotation=self.shown,
            role=MetadataRole.objects.get(slug="when"),
            subject="object",
        )
        existing.annotations.add(self.shown)
        remove = self.client.post(
            reverse("representations:remove-annotation", args=[existing.pk, self.shown.pk])
        )
        self.assertContains(remove, "Suggested")
        self.assertContains(
            self.client.post(reverse("representations:remove-link", args=[link.pk])), "Suggested"
        )
        self.assertTrue(existing.annotations.exists())
        self.assertTrue(RepresentationMetadata.objects.exists())

    def test_pending_markers(self):
        submit(self.user, Kind.LINK, location=self.name, annotation=self.shown)
        review = self.client.get(reverse("reviews:review", args=[self.upload.pk]))
        self.assertContains(review, "1 suggestion")
        self.assertContains(review, "status-dot--pending")
        self.assertContains(review, '<span id="open-count">')
        explorer = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(explorer, "1 suggestion")
        panel = self.client.get(
            reverse("schemas:location", args=["tiktok"]), {"path": self.name.path}
        )
        self.assertContains(panel, "Open suggestions")
        listed = self.client.get(reverse("proposals:for", args=["location", self.name.pk]))
        self.assertContains(listed, "Link to an annotation")
        self.assertContains(listed, "Withdraw")  # the proposer's own
        self.client.logout()
        public = self.client.get(reverse("proposals:for", args=["location", self.name.pk]))
        self.assertContains(public, "Link to an annotation")  # visible to everyone
        self.assertNotContains(public, "Withdraw")


class DecidingTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", is_staff=True)
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.youtube = Platform.objects.create(name="YouTube", slug="youtube")
        parsed_upload(self.platform, DATA, register=True)
        parsed_upload(self.youtube, DATA, register=True)
        self.name = Location.objects.get(platform=self.platform, path="/a.json/name")
        self.email = Location.objects.get(platform=self.platform, path="/a.json/email")
        self.youtube_name = Location.objects.get(platform=self.youtube, path="/a.json/name")
        self.shown = create_annotation(self.email, "Email", self.staff)

    def propose(self, **kwargs):
        proposal = submit(self.user, **kwargs)
        assert proposal is not None
        return proposal

    def test_queues_are_staff_only(self):
        self.client.force_login(self.user)
        for name in ("proposals:annotations", "proposals:representations"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        page = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(page, "My suggestions")
        self.assertNotContains(page, "Suggestions (")

    def test_annotation_queue_by_platform(self):
        tiktok = self.propose(kind=Kind.IGNORE, location=self.name)
        self.propose(kind=Kind.IGNORE, location=self.email)
        youtube = self.propose(kind=Kind.IGNORE, location=self.youtube_name)
        self.client.force_login(self.staff)
        queue = self.client.get(reverse("proposals:annotations"))
        self.assertEqual(queue.context["platform"], self.platform)  # the most first
        self.assertEqual(queue.context["entries"][0]["proposal"], tiktok)
        self.assertContains(queue, "?platform=youtube")
        other = self.client.get(reverse("proposals:annotations"), {"platform": "youtube"})
        self.assertEqual([e["proposal"] for e in other.context["entries"]], [youtube])
        self.assertContains(
            self.client.get(reverse("schemas:platform", args=["tiktok"])), "Suggestions (3)"
        )

    def test_accept_and_reject_one_at_a_time(self):
        accepted = self.propose(kind=Kind.LINK, location=self.name, annotation=self.shown)
        rejected = self.propose(
            kind=Kind.EDIT_ANNOTATION, annotation=self.shown, values={"name": "Mail"}
        )
        self.client.force_login(self.user)
        url = reverse("proposals:decide", args=[accepted.pk, "accept"])
        self.assertEqual(self.client.post(url).status_code, 302)  # staff only
        self.client.force_login(self.staff)
        response = self.client.post(url)
        self.assertContains(response, "Accepted by admin")
        self.assertEqual(
            response["HX-Trigger"],
            f"triaged-{self.name.pk}, representations-changed-{self.shown.pk}",
        )
        self.assertEqual(Location.objects.get(pk=self.name.pk).annotation, self.shown)
        reject = self.client.post(
            reverse("proposals:decide", args=[rejected.pk, "reject"]), {"reason": "Not a mail."}
        )
        self.assertContains(reject, "Rejected by admin")
        self.assertContains(reject, "Not a mail.")
        again = self.client.post(url)
        self.assertContains(again, "decided already")

    def test_stale_needs_confirming(self):
        proposal = self.propose(kind=Kind.LINK, location=self.name, annotation=self.shown)
        Annotation.objects.create(platform=self.platform, name="Other")
        create_annotation(self.name, "Changed", self.staff)
        self.client.force_login(self.staff)
        url = reverse("proposals:decide", args=[proposal.pk, "accept"])
        first = self.client.post(url)
        self.assertContains(first, "accept anyway?")
        self.assertContains(first, 'name="stale" value="1"')
        self.assertContains(self.client.post(url, {"stale": "1"}), "Accepted")

    def test_mine_and_withdraw(self):
        proposal = self.propose(kind=Kind.IGNORE, location=self.name)
        other = User.objects.create_user("other")
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse("proposals:mine")), "Not a data point")
        withdraw = reverse("proposals:withdraw", args=[proposal.pk])
        self.assertEqual(self.client.post(withdraw).status_code, 403)
        self.client.force_login(self.user)
        mine = self.client.get(reverse("proposals:mine"))
        self.assertContains(mine, "Not a data point")
        self.assertContains(self.client.post(withdraw), "Withdrawn")

    def test_representation_queue(self):
        video = ObjectType.objects.get(slug="video")
        self.propose(
            kind=Kind.NEW_REPRESENTATION,
            values={"pattern": Pattern.OBJECT, "name": "Video", "object": video.pk},
        )
        self.client.force_login(self.staff)
        queue = self.client.get(reverse("proposals:representations"))
        self.assertContains(queue, "New representation")
        self.assertContains(queue, "Video")
        self.assertContains(queue, "data-proposals")
