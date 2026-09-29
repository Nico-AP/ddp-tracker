from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import accept, changes
from ddp_tracker.representations.forms import RepresentationForm, TermField
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.representations.services import describe, suggest_term
from ddp_tracker.representations.tests.fixtures import WatchHistory
from ddp_tracker.users.models import User

Subject = RepresentationMetadata.Subject


class ViewTestCase(WatchHistory, TestCase):
    def setUp(self):
        self.curator = User.objects.create_user("curator", is_staff=True)  # staff decide directly
        self.other = User.objects.create_user("other")
        self.user = ActorType.objects.get(slug="user")
        self.view = ActivityType.objects.get(slug="viewed")
        self.video = ObjectType.objects.get(slug="video")
        self.collection = ObjectType.objects.get(slug="collection")
        self.when = MetadataRole.objects.get(slug="when")
        self.add_watch_history(Platform.objects.create(name="TikTok", slug="tiktok"))
        self.watched = Representation.objects.create(
            location=self.item,
            pattern=Pattern.ACTIVITY,
            name="Watched video",
            actor=self.user,
            activity=self.view,
            object=self.video,
        )

    def form_data(self, **fields):
        return {"pattern": Pattern.ACTIVITY, "name": "X", "description": "", "note": ""} | {
            key: getattr(value, "pk", value) for key, value in fields.items()
        }

    def section(self, location):
        return self.client.get(reverse("representations:location-section", args=[location.pk]))


class PublicPagesTests(ViewTestCase):
    def test_list_and_detail(self):
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        describe(self.watched, self.author_name, MetadataRole.objects.get(slug="name"), "object")
        self.item.annotation = Annotation.objects.create(platform=self.platform, name="Watched")
        self.item.save()
        listing = self.client.get(reverse("representations:representations"))
        self.assertContains(listing, "user · viewed · video")
        self.assertContains(listing, "<td>TikTok</td>", html=True)
        self.assertContains(listing, f"<td><code>{self.item.path}</code></td>", html=True)
        self.assertContains(listing, "<td>2</td>", html=True)
        detail = self.client.get(self.watched.get_absolute_url())
        self.assertContains(detail, self.item.path)
        self.assertContains(detail, "Annotated as")
        self.assertContains(detail, "<code>Author/Name</code>", html=True)
        self.assertNotContains(detail, "Remove")
        self.assertNotContains(detail, ">Edit<")
        # grouped by subject, in the slots' order
        self.assertEqual(
            [
                (subject, [str(link.role) for link in links])
                for subject, links in detail.context["described"]
            ],
            [("activity", ["when"]), ("object", ["name"])],
        )

    def test_empty_pages(self):
        self.assertContains(self.client.get(self.watched.get_absolute_url()), "None yet")
        Representation.objects.all().delete()
        self.assertContains(
            self.client.get(reverse("representations:representations")), "No representations"
        )
        missing = reverse("representations:representation", args=[self.watched.pk + 1])
        self.assertEqual(self.client.get(missing).status_code, 404)

    def test_section_is_read_only_for_visitors(self):
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        response = self.section(self.item)
        self.assertContains(response, self.watched.get_absolute_url())
        self.assertContains(response, "<code>Date</code>: <em>when</em> of the activity", html=True)
        for text in ("Add representation", "Edit", "Suggest a change", "hx-post"):
            self.assertNotContains(response, text)

    def test_section_without_representations(self):
        self.watched.delete()
        self.assertContains(self.section(self.item), "No representation yet")
        # not annotated: no matter
        self.assertIsNone(self.item.annotation)
        for location in (self.date, self.elsewhere, self.tag):
            with self.subTest(path=location.path):
                self.assertContains(
                    self.section(location), "Representations are for the items of lists of objects"
                )


def sections(**rows):
    """The dialog's metadata formsets' data: per slot, ``rows`` of (location, role)."""
    data: dict[str, object] = {}
    for subject in ("actor", "activity", "object", "target"):
        prefix = f"metadata-{subject}"
        filled = rows.get(subject, [])
        data |= {f"{prefix}-TOTAL_FORMS": str(len(filled)), f"{prefix}-INITIAL_FORMS": "0"}
        for index, (location, role) in enumerate(filled):
            data |= {
                f"{prefix}-{index}-location": getattr(location, "pk", location),
                f"{prefix}-{index}-role": getattr(role, "pk", role),
            }
    return data


class CurationTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.curator)

    def test_changes_need_a_login(self):
        self.client.logout()
        for url in (
            reverse("representations:edit", args=[self.watched.pk]),
            reverse("representations:add", args=[self.item.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        delete = reverse("representations:delete", args=[self.watched.pk])
        self.assertEqual(self.client.post(delete).status_code, 302)

    def test_section_for_curators(self):
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        response = self.section(self.item)
        self.assertContains(response, "Add representation")
        self.assertContains(response, reverse("representations:edit", args=[self.watched.pk]))
        # read-only: changes happen in the dialog
        for text in ("Add metadata", "Delete", "hx-post"):
            self.assertNotContains(response, text)
        self.assertNotContains(self.section(self.date), "Add representation")

    def assert_changed(self, response, location):
        """Staff's change from the dialog: it closes (no content), and the section reloads."""
        self.assertEqual(response.content, b"")
        self.assertEqual(response["HX-Trigger"], f"representations-changed-{location.pk}")

    def test_new_dialog(self):
        modal = self.client.get(reverse("representations:add", args=[self.item.pk]))
        # a fixed header with a small close button; the rest is the scrolling body
        self.assertContains(
            modal, '<button type="submit" class="btn-close" aria-label="Close"></button>', html=True
        )
        self.assertContains(modal, '<div class="dialog__body">')
        self.assertContains(modal, self.item.path)
        for text in ("Something happened", "Something exists", "Actor metadata", "Target metadata"):
            self.assertContains(modal, text)
        self.assertNotContains(modal, "Delete this representation")  # nothing to delete yet
        # per slot a formset: its rows (data point, then role) and a template to add one
        for subject in ("actor", "activity", "object", "target"):
            self.assertContains(modal, f'name="metadata-{subject}-TOTAL_FORMS"')
            self.assertContains(modal, f"metadata-{subject}-__prefix__-location")
        self.assertNotContains(modal, "-subject")
        content = modal.content.decode()
        self.assertLess(
            content.index("metadata-actor-__prefix__-location"),
            content.index("metadata-actor-__prefix__-role"),
        )
        self.assertContains(
            modal,
            f'<option value="{self.author_name.pk}">history/[]/Author/Name</option>',
            html=True,
        )
        self.assertNotContains(modal, self.elsewhere.path)
        # only for locations that can have one
        response = self.client.get(reverse("representations:add", args=[self.date.pk]))
        self.assertEqual(response.status_code, 404)

    def test_create_with_metadata(self):
        url = reverse("representations:add", args=[self.item.pk])
        video = self.form_data(pattern=Pattern.OBJECT, name="Video", object=self.video)
        # a partly filled row
        response = self.client.post(url, video | sections(object=[(self.date, "")]))
        self.assertContains(response, "needs a data point and a role")
        # a location outside the item
        response = self.client.post(url, video | sections(object=[(self.elsewhere, self.when)]))
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(Representation.objects.filter(name="Video").exists())
        # rows of a slot the pattern hides are dropped; an empty row is skipped
        self.assert_changed(
            self.client.post(
                url,
                video
                | sections(
                    object=[(self.date, self.when), ("", "")],
                    activity=[(self.link, self.when)],
                ),
            ),
            self.item,
        )
        created = Representation.objects.get(name="Video")
        self.assertEqual((created.updated_by, created.location), (self.curator, self.item))
        self.assertEqual(
            list(created.metadata_links.values_list("subject", "location__path")),
            [("object", self.date.path)],
        )
        # the names needn't be unique
        self.assert_changed(self.client.post(url, video | sections()), self.item)
        self.assertEqual(Representation.objects.filter(name="Video").count(), 2)

    def test_create_activity_and_unmapped(self):
        url = reverse("representations:add", args=[self.item.pk])
        activity = self.form_data(
            name="Watched with", actor=self.user, activity=self.view, object=self.video
        )
        # target metadata needs a target
        response = self.client.post(url, activity | sections(target=[(self.date, self.when)]))
        self.assertContains(response, "1 metadata link describe the target.")
        activity |= {"target": self.collection.pk}
        self.assert_changed(
            self.client.post(url, activity | sections(target=[(self.date, self.when)])),
            self.item,
        )
        created = Representation.objects.get(name="Watched with")
        self.assertEqual(created.statement, "user · viewed · video · collection")
        self.assertEqual(created.metadata_links.get().subject, "target")
        unmapped = self.form_data(pattern=Pattern.UNMAPPED, name="Unclear")
        self.assert_changed(
            self.client.post(url, unmapped | sections(object=[(self.date, self.when)])),
            self.item,
        )
        unclear = Representation.objects.get(name="Unclear")
        self.assertFalse(unclear.metadata_links.exists())  # no slots: its rows are dropped

    def test_create_as_a_suggestion(self):
        self.client.force_login(self.other)
        url = reverse("representations:add", args=[self.item.pk])
        data = self.form_data(pattern=Pattern.OBJECT, name="Video", object=self.video)
        response = self.client.post(url, data | sections(object=[(self.link, self.when)]))
        self.assertContains(response, "staff will review your suggestion")  # the dialog says so
        self.assertEqual(response["HX-Trigger"], f"representations-changed-{self.item.pk}")
        self.assertFalse(Representation.objects.filter(name="Video").exists())
        proposal = Proposal.objects.get(kind=Proposal.Kind.NEW_REPRESENTATION)
        self.assertEqual((proposal.location, proposal.platform), (self.item, self.platform))
        accept(proposal, self.curator)
        created = Representation.objects.get(name="Video")
        self.assertEqual((created.location, created.updated_by), (self.item, self.other))
        self.assertEqual([link.location for link in created.metadata_links.all()], [self.link])

    def test_edit_dialog(self):
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        url = reverse("representations:edit", args=[self.watched.pk])
        modal = self.client.get(url)
        self.assertContains(modal, "Edit representation")
        self.assertContains(modal, "Delete this representation")
        self.assertContains(modal, 'value="Watched video"')
        # its links are the rows of their slot
        self.assertContains(modal, 'name="metadata-activity-TOTAL_FORMS" value="1"')
        self.assertContains(
            modal, f'<option value="{self.date.pk}" selected>history/[]/Date</option>', html=True
        )

    def test_edit_replaces_the_metadata(self):
        name = MetadataRole.objects.get(slug="name")
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        describe(self.watched, self.author_name, name, Subject.ACTOR)
        url = reverse("representations:edit", args=[self.watched.pk])
        data = self.form_data(
            name="Watched a video",
            actor=self.user,
            activity=self.view,
            object=self.video,
            target=self.collection,
        )
        # the date is kept, the author's name removed, the link added
        rows = sections(activity=[(self.date, self.when)], object=[(self.link, self.when)])
        rows["metadata-activity-INITIAL_FORMS"] = "1"  # as the dialog shows the saved one
        self.assert_changed(self.client.post(url, data | rows), self.item)
        self.watched.refresh_from_db()
        self.assertEqual(
            (self.watched.name, self.watched.updated_by, self.watched.location),
            ("Watched a video", self.curator, self.item),
        )
        self.assertEqual(self.watched.statement, "user · viewed · video · collection")
        self.assertEqual(
            sorted(self.watched.metadata_links.values_list("subject", "location__path")),
            [("activity", self.date.path), ("object", self.link.path)],
        )

    def test_edit_can_empty_a_slot_with_its_metadata(self):
        describe(self.watched, self.date, MetadataRole.objects.get(slug="name"), Subject.ACTOR)
        url = reverse("representations:edit", args=[self.watched.pk])
        video = self.form_data(name="Video", pattern=Pattern.OBJECT, object=self.video)
        # the actor's rows are hidden with it: dropped, so the actor can go
        self.assert_changed(
            self.client.post(url, video | sections(actor=[(self.date, self.when)])), self.item
        )
        self.watched.refresh_from_db()
        self.assertEqual((self.watched.pattern, self.watched.actor), (Pattern.OBJECT, None))
        self.assertFalse(self.watched.metadata_links.exists())

    def test_edit_as_a_suggestion(self):
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        self.client.force_login(self.other)
        url = reverse("representations:edit", args=[self.watched.pk])
        self.assertContains(self.client.get(url), "Suggest a change")
        data = self.form_data(actor=self.user, activity=self.view, object=self.video)
        self.client.post(url, data | sections(object=[(self.link, self.when)]))
        self.assertEqual(self.watched.metadata_links.get().location, self.date)  # unchanged
        proposal = Proposal.objects.get(kind=Proposal.Kind.EDIT_REPRESENTATION)
        described = [row for row in changes(proposal) if row[0] == "Metadata"]
        self.assertEqual(
            described,
            [
                ("Metadata", f"{self.date.path}: when of the activity", "none"),
                ("Metadata", "", f"{self.link.path}: when of the object"),
            ],
        )
        accept(proposal, self.curator)
        self.assertEqual(self.watched.metadata_links.get().location, self.link)

    def test_delete(self):
        # from the side panel's dialog: it closes, the section reloads
        self.assert_changed(
            self.client.post(reverse("representations:delete", args=[self.watched.pk])),
            self.item,
        )
        self.assertFalse(Representation.objects.exists())
        # on its own page: back to the list
        other = Representation.objects.create(
            location=self.item, pattern=Pattern.UNMAPPED, name="Other"
        )
        response = self.client.post(
            reverse("representations:delete", args=[other.pk]),
            headers={"hx-current-url": f"http://testserver{other.get_absolute_url()}"},
        )
        self.assertEqual(response["HX-Redirect"], reverse("representations:representations"))

    def test_delete_as_a_suggestion(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("representations:delete", args=[self.watched.pk]))
        self.assertContains(response, "staff will review your suggestion")
        proposal = Proposal.objects.get(kind=Proposal.Kind.DELETE_REPRESENTATION)
        self.assertEqual(proposal.location, self.item)
        accept(proposal, self.curator)
        self.assertFalse(Representation.objects.exists())
        proposal.refresh_from_db()
        self.assertEqual(proposal.values, {"representation": "Watched video"})

    def test_the_page_opens_the_dialog(self):
        page = self.client.get(self.watched.get_absolute_url())
        self.assertContains(page, reverse("representations:edit", args=[self.watched.pk]))
        self.assertContains(page, f"representations-changed-{self.item.pk} from:body")


class VocabularyTests(ViewTestCase):
    def test_public_page_lists_approved_terms_only(self):
        suggest_term(ObjectType, "Livestream", "A live broadcast.", self.curator)
        response = self.client.get(reverse("representations:vocabulary"))
        self.assertContains(response, "A video.")
        self.assertNotContains(response, "Livestream")
        self.assertNotContains(response, "Suggest a term")
        rows = {
            vocabulary["title"]: {term.slug: term.usage for term in vocabulary["terms"]}
            for vocabulary in response.context["vocabularies"]
        }
        self.assertEqual(rows["Object types"]["video"], 1)
        self.assertEqual(rows["Actor types"]["user"], 1)

    def test_suggest(self):
        url = reverse("representations:suggest")
        self.assertEqual(self.client.post(url, {}).status_code, 302)  # login first
        self.client.force_login(self.curator)
        page = self.client.get(reverse("representations:vocabulary"))
        self.assertContains(page, "Suggest a term")
        data = {"kind": "object", "name": "Livestream", "description": "A live broadcast."}
        response = self.client.post(url, data, follow=True)
        self.assertContains(response, "awaits approval")
        self.assertContains(response, "pending")
        term = ObjectType.objects.get(slug="livestream")
        self.assertEqual((term.approved, term.created_by), (False, self.curator))
        for name in ("livestream", "Video", "…"):
            with self.subTest(name=name):
                self.assertContains(self.client.post(url, data | {"name": name}), "form__error")

    def test_pending_terms_are_offered_to_their_suggester_only(self):
        livestream = suggest_term(ObjectType, "Livestream", "A live broadcast.", self.curator)

        def field(user, instance=None):
            found = RepresentationForm(user=user, instance=instance).fields["object"]
            assert isinstance(found, TermField)
            return found

        self.assertIn(livestream, field(self.curator).queryset)
        self.assertEqual(
            field(self.curator).label_from_instance(livestream), "Livestream (suggested)"
        )
        self.assertNotIn(livestream, field(self.other).queryset)
        # once in use, others can still edit the representation
        live = Representation.objects.create(
            location=self.item, pattern=Pattern.OBJECT, name="Live", object=livestream
        )
        self.assertIn(livestream, field(self.other, live).queryset)

    def test_admin_approves(self):
        term = suggest_term(ObjectType, "Livestream", "A live broadcast.", self.curator)
        self.client.force_login(User.objects.create_superuser("admin"))
        page = self.client.get(reverse("representations:vocabulary"))
        self.assertContains(page, "1 suggestion to review")
        response = self.client.post(
            reverse("admin:representations_objecttype_changelist"),
            {"action": "approve", "_selected_action": [term.pk]},
            follow=True,
        )
        self.assertContains(response, "Approved 1 term.")
        term.refresh_from_db()
        self.assertTrue(term.approved)
        self.assertContains(self.client.get(reverse("representations:vocabulary")), "Livestream")
