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
        self.upload = parsed_upload(self.platform, DATA, register=True, user=self.user)
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
        when = MetadataRole.objects.get(slug="when")
        item = Location.objects.get(path="/a.json/videos/[]")
        at = Location.objects.get(path="/a.json/videos/[]/when")
        management = {
            f"metadata-{subject}-{count}": "0"
            for subject in ("actor", "activity", "object", "target")
            for count in ("TOTAL_FORMS", "INITIAL_FORMS")
        }
        response = self.client.post(
            reverse("representations:add", args=[item.pk]),
            management
            | {
                "pattern": Pattern.OBJECT,
                "name": "Video",
                "object": video.pk,
                "metadata-object-TOTAL_FORMS": "1",
                "metadata-object-0-location": at.pk,
                "metadata-object-0-role": when.pk,
            },
        )
        self.assertContains(response, "staff will review your suggestion")
        self.assertEqual(response["HX-Trigger"], f"representations-changed-{item.pk}")
        self.assertFalse(Representation.objects.exists())
        suggested = Proposal.objects.get(kind=Kind.NEW_REPRESENTATION)
        self.assertEqual(
            suggested.values["metadata"],
            [{"subject": "object", "role": when.pk, "location": at.pk}],
        )
        self.assertIn("Metadata", [field for field, _, _ in changes(suggested)])
        existing = Representation.objects.create(
            location=item, pattern=Pattern.OBJECT, name="Clip", object=video
        )
        RepresentationMetadata.objects.create(
            representation=existing, location=at, role=when, subject="object"
        )
        edit = self.client.post(
            reverse("representations:edit", args=[existing.pk]),
            management | {"pattern": Pattern.OBJECT, "name": "Short clip", "object": video.pk},
        )
        self.assertContains(edit, "staff will review your suggestion")
        existing.refresh_from_db()
        self.assertEqual(existing.name, "Clip")
        self.assertTrue(existing.metadata_links.exists())  # the suggestion removes it, later
        self.assertContains(
            self.client.post(reverse("representations:delete", args=[existing.pk])),
            "staff will review your suggestion",
        )
        self.assertTrue(Representation.objects.filter(pk=existing.pk).exists())
        self.assertEqual(
            sorted(Proposal.objects.values_list("kind", flat=True)),
            sorted(
                [
                    Kind.NEW_REPRESENTATION,
                    Kind.EDIT_REPRESENTATION,
                    Kind.DELETE_REPRESENTATION,
                ]
            ),
        )

    def test_pending_markers(self):
        submit(self.user, Kind.LINK, location=self.name, annotation=self.shown)
        review = self.client.get(reverse("reviews:review", args=[self.upload.pk]))
        self.assertContains(review, "1 suggestion")
        self.assertContains(review, "status-dot--pending")
        self.assertContains(review, '<span id="open-count">')
        explorer = self.client.get(reverse("schemas:platform", args=["tiktok"]))
        self.assertContains(explorer, "1 suggestion")

    def test_the_suggestion_is_its_proposers_and_staffs(self):
        """Everyone sees that a suggestion is open; what it is, only its proposer and staff."""
        url = reverse("schemas:triage", args=[self.name.pk])
        self.client.post(url, {"action": "new", "name": "Display name", "upload": self.upload.pk})
        panel_url = reverse("schemas:location", args=["tiktok"])
        review_panel = reverse("reviews:location", args=[self.upload.pk, self.name.pk])
        listed = reverse("proposals:for", args=["location", self.name.pk])
        # the marker, where the annotation is, for everyone
        for panel in (
            self.client.get(panel_url, {"path": self.name.path}),
            self.client.get(review_panel),
        ):
            self.assertContains(panel, "Suggestion open")  # the header chip is the marker
            self.assertNotContains(panel, "open suggestion")  # no second one below
            self.assertNotContains(panel, "Not annotated yet")
            # the proposer's own, under a heading
            self.assertContains(
                panel, '<h3 class="review-panel__label mt-3">Suggestions</h3>', html=True
            )
            self.assertContains(panel, listed)
        own = self.client.get(listed)
        self.assertContains(own, "Display name")
        self.assertContains(own, "Withdraw")
        # in the panel, the path is clear from the context; elsewhere it says which data point
        self.assertNotContains(own, 'class="proposal__target"')
        self.assertContains(own, 'name="in_panel" value="1"')  # kept after withdrawing
        mine = self.client.get(reverse("proposals:mine"))
        self.assertContains(
            mine, f'<code class="proposal__target">{self.name.path}</code>', html=True
        )
        self.assertContains(own, f"by #{self.user.pk}")  # never the email
        self.assertNotContains(own, self.user.email)
        # someone else: the marker, not what is suggested
        self.client.force_login(User.objects.create_user("someone@example.test"))
        other = self.client.get(panel_url, {"path": self.name.path})
        self.assertContains(other, "Suggestion open")
        self.assertNotContains(other, "Display name")
        self.assertNotContains(other, listed)  # none of theirs: no heading, nothing to load
        self.assertNotContains(
            other, '<h3 class="review-panel__label mt-3">Suggestions</h3>', html=True
        )
        self.assertNotContains(self.client.get(listed), "Display name")
        self.client.logout()
        public = self.client.get(panel_url, {"path": self.name.path})
        self.assertContains(public, "Suggestion open")
        self.assertNotContains(public, listed)  # nothing to load
        self.assertNotContains(self.client.get(listed), "Display name")
        # staff: all of them, to decide; a decision in the panel keeps it without the path
        self.client.force_login(self.staff)
        staff_panel = self.client.get(panel_url, {"path": self.name.path})
        self.assertContains(
            staff_panel, '<h3 class="review-panel__label mt-3">Suggestions</h3>', html=True
        )
        self.assertContains(self.client.get(listed), "Display name")
        proposal = Proposal.objects.get(kind=Kind.NEW_ANNOTATION)
        decided = self.client.post(
            reverse("proposals:decide", args=[proposal.pk, "reject"]),
            {"reason": "Not now.", "in_panel": "1"},
        )
        self.assertContains(decided, f"Rejected by #{self.staff.pk}")
        self.assertNotContains(decided, 'class="proposal__target"')

    def test_representation_suggestions_likewise(self):
        video = ObjectType.objects.get(slug="video")
        item = Location.objects.get(path="/a.json/videos/[]")
        submit(
            self.user,
            Kind.NEW_REPRESENTATION,
            location=item,
            values={"pattern": Pattern.OBJECT, "name": "Watched clip", "object": video.pk},
        )
        existing = Representation.objects.create(
            location=item, pattern=Pattern.OBJECT, name="Clip", object=video
        )
        submit(self.user, Kind.DELETE_REPRESENTATION, representation=existing, location=item)
        section = reverse("representations:location-section", args=[item.pk])
        listed = reverse("proposals:for", args=["location-representations", item.pk])
        page = existing.get_absolute_url()
        own_section = self.client.get(section)
        self.assertContains(own_section, "2 open suggestions")
        self.assertContains(
            own_section, '<h3 class="review-panel__label mt-3">Suggestions</h3>', html=True
        )
        own = self.client.get(listed)
        self.assertContains(own, "Watched clip")
        self.assertContains(own, "Delete the representation")
        self.assertContains(self.client.get(page), "Open suggestions (1)")
        self.client.logout()
        self.assertContains(self.client.get(section), "2 open suggestions")
        self.assertNotContains(self.client.get(section), ">Suggestions</h3>")
        self.assertNotContains(self.client.get(section), listed)
        self.assertNotContains(self.client.get(listed), "Watched clip")
        public_page = self.client.get(page)
        self.assertContains(public_page, "Open suggestions (1)")
        self.assertNotContains(
            public_page, reverse("proposals:for", args=["representation", existing.pk])
        )
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(listed), "Watched clip")


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
        self.assertContains(response, f"Accepted by #{self.staff.pk}")  # not by email
        self.assertEqual(response["HX-Trigger"], f"triaged-{self.name.pk}")
        self.assertEqual(Location.objects.get(pk=self.name.pk).annotation, self.shown)
        reject = self.client.post(
            reverse("proposals:decide", args=[rejected.pk, "reject"]), {"reason": "Not a mail."}
        )
        self.assertContains(reject, f"Rejected by #{self.staff.pk}")
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
        item = Location.objects.get(platform=self.platform, path="/a.json/videos/[]")
        proposal = self.propose(
            kind=Kind.NEW_REPRESENTATION,
            location=item,
            values={"pattern": Pattern.OBJECT, "name": "Video", "object": video.pk},
        )
        self.client.force_login(self.staff)
        queue = self.client.get(reverse("proposals:representations"))
        self.assertContains(queue, "New representation")
        self.assertContains(queue, "Video")
        self.assertContains(queue, "data-proposals")
        response = self.client.post(reverse("proposals:decide", args=[proposal.pk, "accept"]))
        self.assertEqual(
            response["HX-Trigger"], f"triaged-{item.pk}, representations-changed-{item.pk}"
        )
        created = Representation.objects.get()
        delete = self.propose(kind=Kind.DELETE_REPRESENTATION, representation=created)
        response = self.client.post(reverse("proposals:decide", args=[delete.pk, "reject"]))
        self.assertEqual(response["HX-Trigger"], f"representations-changed-{item.pk}")
