from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
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
from ddp_tracker.representations.services import describe, represent, suggest_term
from ddp_tracker.schemas.models import Location
from ddp_tracker.users.models import User

Subject = RepresentationMetadata.Subject


class ViewTestCase(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user("curator", is_staff=True)  # staff decide directly
        self.other = User.objects.create_user("other")
        self.user = ActorType.objects.get(slug="user")
        self.view = ActivityType.objects.get(slug="view")
        self.video = ObjectType.objects.get(slug="video")
        self.collection = ObjectType.objects.get(slug="collection")
        self.when = MetadataRole.objects.get(slug="when")
        self.tiktok = Platform.objects.create(name="TikTok", slug="tiktok")
        self.youtube = Platform.objects.create(name="YouTube", slug="youtube")
        self.item = Annotation.objects.create(platform=self.tiktok, name="watch_history item")
        self.date = Annotation.objects.create(platform=self.tiktok, name="Date")
        self.time = Annotation.objects.create(platform=self.youtube, name="time")
        self.watched = Representation.objects.create(
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


class PublicPagesTests(ViewTestCase):
    def test_list_and_detail(self):
        represent(self.watched, self.item)
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        describe(self.watched, self.time, self.when, Subject.ACTIVITY)
        listing = self.client.get(reverse("representations:representations"))
        self.assertContains(listing, "user · view · video")
        self.assertContains(listing, "<td>TikTok, YouTube</td>", html=True)
        self.assertNotContains(listing, "New representation")
        detail = self.client.get(self.watched.get_absolute_url())
        self.assertContains(detail, "watch_history item")
        self.assertNotContains(detail, "Remove")
        self.assertNotContains(detail, ">Edit<")
        # the matrix: one row (activity, when), a column per platform
        matrix = detail.context["matrix"]
        self.assertEqual(
            [(row["subject"], str(row["role"])) for row in matrix], [("activity", "when")]
        )
        self.assertEqual(
            [[str(link.annotation) for link in cell] for cell in matrix[0]["cells"]],
            [["Date"], ["time"]],
        )
        self.assertEqual([str(p) for p in detail.context["platforms"]], ["TikTok", "YouTube"])

    def test_matrix_rows_follow_the_slot_order(self):
        added = Representation.objects.create(
            pattern=Pattern.ACTIVITY,
            name="Added",
            actor=self.user,
            activity=ActivityType.objects.get(slug="add"),
            object=self.video,
            target=self.collection,
        )
        name = MetadataRole.objects.get(slug="name")
        describe(added, self.date, name, Subject.TARGET)
        describe(added, self.date, self.when, Subject.ACTIVITY)
        describe(added, self.date, name, Subject.OBJECT)
        matrix = self.client.get(added.get_absolute_url()).context["matrix"]
        self.assertEqual([row["subject"] for row in matrix], ["activity", "object", "target"])

    def test_empty_pages(self):
        self.assertContains(self.client.get(self.watched.get_absolute_url()), "None yet")
        Representation.objects.all().delete()
        self.assertContains(
            self.client.get(reverse("representations:representations")), "No representations"
        )
        missing = reverse("representations:details", args=[self.watched.pk + 1])
        self.assertEqual(self.client.get(missing).status_code, 404)

    def test_annotation_page_section_is_read_only_for_visitors(self):
        represent(self.watched, self.item)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, "<td>is it</td>", html=True)
        self.assertContains(response, self.watched.get_absolute_url())
        self.assertNotContains(response, "Add representation")
        self.assertNotContains(response, "Remove")
        self.assertContains(self.client.get(self.date.get_absolute_url()), "Not linked")

    def test_sections(self):
        represent(self.watched, self.item)
        describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        url = reverse("representations:annotation-section", args=[self.date.pk])
        panel = self.client.get(url, {"layout": "panel"})
        self.assertContains(panel, "Describes the <em>when</em> of the activity in")
        self.assertNotContains(panel, "<table")
        self.assertContains(self.client.get(url), "<table")  # the page layout by default
        # the explorer's side panel: via the location's annotation
        location = Location.objects.create(platform=self.tiktok, path="/a.json/at", name="at")
        location_url = reverse("representations:location-section", args=[location.pk])
        self.assertContains(self.client.get(location_url), "Assign an annotation first")
        location.annotation = self.date
        location.save()
        self.assertContains(self.client.get(location_url), "Watched video")


class CurationTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.curator)

    def test_changes_need_a_login(self):
        self.client.logout()
        urls = [
            reverse("representations:create"),
            reverse("representations:edit", args=[self.watched.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        represent_url = reverse("representations:represent", args=[self.item.pk])
        self.assertEqual(self.client.post(represent_url).status_code, 302)

    def test_create(self):
        url = reverse("representations:create")
        self.assertContains(self.client.get(url), "representation-form")
        self.assertNotContains(self.client.get(url), 'name="pattern" value=""')
        response = self.client.post(url, self.form_data(name="Video", pattern=Pattern.OBJECT))
        self.assertContains(response, "Required for something exists.")
        response = self.client.post(
            url,
            self.form_data(
                name="Video",
                pattern=Pattern.OBJECT,
                object=self.video,
                actor=self.user,  # hidden for objects: dropped
            ),
        )
        video = Representation.objects.get(name="Video")
        self.assertRedirects(response, video.get_absolute_url())
        self.assertEqual((video.actor, video.updated_by), (None, self.curator))

    def test_edit(self):
        url = reverse("representations:edit", args=[self.watched.pk])
        self.assertContains(self.client.get(url), "Edit Watched video")
        response = self.client.post(
            url,
            self.form_data(
                name="Watched a video",
                actor=self.user,
                activity=self.view,
                object=self.video,
                target=self.collection,
            ),
        )
        self.assertContains(response, "user · view · video · collection")
        self.watched.refresh_from_db()
        self.assertEqual(
            (self.watched.name, self.watched.updated_by), ("Watched a video", self.curator)
        )
        self.assertContains(
            self.client.get(reverse("representations:details", args=[self.watched.pk])),
            "user · view · video · collection",
        )

    def test_edit_keeps_slots_in_use(self):
        describe(self.watched, self.date, MetadataRole.objects.get(slug="name"), Subject.ACTOR)
        response = self.client.post(
            reverse("representations:edit", args=[self.watched.pk]),
            self.form_data(name="Video", pattern=Pattern.OBJECT, object=self.video),
        )
        self.assertContains(response, "1 metadata link describe the actor")

    def assert_changed(self, response, annotation):
        """A successful change from the modal: no content, and the lists reload."""
        self.assertEqual(response.content, b"")
        self.assertEqual(response["HX-Trigger"], f"representations-changed-{annotation.pk}")

    def test_modal(self):
        page = self.client.get(self.item.get_absolute_url())
        self.assertContains(page, "Add representation")
        self.assertNotContains(page, "This data point is")  # only in the modal
        modal = self.client.get(reverse("representations:add", args=[self.item.pk]))
        for text in ("This data point is", "This data point describes", "Create and link"):
            self.assertContains(modal, text)
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("representations:add", args=[self.item.pk])).status_code, 302
        )

    def test_represent(self):
        url = reverse("representations:represent", args=[self.item.pk])
        self.assert_changed(self.client.post(url, {"representation": self.watched.pk}), self.item)
        self.assertEqual(list(self.watched.annotations.all()), [self.item])
        # linked already: no longer offered, the modal comes back with the error
        response = self.client.post(url, {"representation": self.watched.pk})
        self.assertContains(response, "form__error")
        self.assertContains(response, "Add representation")

    def test_describe(self):
        url = reverse("representations:describe", args=[self.date.pk])
        data = {"representation": self.watched.pk, "role": self.when.pk}
        response = self.client.post(url, data | {"subject": Subject.TARGET})
        self.assertContains(response, "This representation has no target.")
        self.assert_changed(self.client.post(url, data | {"subject": Subject.ACTIVITY}), self.date)
        response = self.client.post(url, data | {"subject": Subject.ACTIVITY})
        self.assertContains(response, "already exists")

    def test_create_and_link(self):
        url = reverse("representations:create-linked", args=[self.date.pk])
        video = {"pattern": Pattern.OBJECT, "name": "Video", "object": self.video.pk}
        data = self.form_data(**video)
        response = self.client.post(url, data | {"relation": "describes"})
        self.assertContains(response, "Required to describe it.")
        # describing a slot the new representation doesn't fill: nothing is created
        response = self.client.post(
            url,
            data | {"relation": "describes", "role": self.when.pk, "subject": Subject.ACTIVITY},
        )
        self.assertContains(response, "This representation has no activity.")
        self.assertFalse(Representation.objects.filter(name="Video").exists())
        self.assert_changed(
            self.client.post(
                url,
                data | {"relation": "describes", "role": self.when.pk, "subject": Subject.OBJECT},
            ),
            self.date,
        )
        created = Representation.objects.get(name="Video")
        self.assertEqual(created.updated_by, self.curator)
        self.assertEqual(list(created.metadata_links.values_list("subject", flat=True)), ["object"])
        response = self.client.post(
            reverse("representations:create-linked", args=[self.item.pk]),
            self.form_data(pattern=Pattern.UNMAPPED, name="Unclear", relation="represents"),
        )
        self.assert_changed(response, self.item)
        self.assertEqual(
            list(self.item.representations.all()), [Representation.objects.get(name="Unclear")]
        )

    def test_remove(self):
        represent(self.watched, self.item)
        link = describe(self.watched, self.date, self.when, Subject.ACTIVITY)
        self.assertContains(self.client.get(self.watched.get_absolute_url()), "Remove")
        self.client.post(
            reverse("representations:remove-annotation", args=[self.watched.pk, self.item.pk])
        )
        self.client.post(reverse("representations:remove-link", args=[link.pk]))
        self.assertFalse(self.watched.annotations.exists())
        self.assertFalse(self.watched.metadata_links.exists())


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
        live = Representation.objects.create(pattern=Pattern.OBJECT, name="Live", object=livestream)
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
