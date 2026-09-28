from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.representations.services import describe
from ddp_tracker.users.models import User

Subject = RepresentationMetadata.Subject


class VocabularyTests(TestCase):
    def test_seeded(self):
        self.assertEqual(
            set(ActorType.objects.values_list("slug", flat=True)),
            {"user", "other-user", "platform"},
        )
        self.assertTrue(ActivityType.objects.filter(slug="viewed").exists())
        self.assertTrue(ObjectType.objects.filter(slug="video").exists())
        applies_to = MetadataRole.objects.get(slug="applies-to")
        self.assertEqual(applies_to.name, "applies to")
        self.assertIn("replies to", applies_to.description)
        self.assertFalse(MetadataRole.objects.filter(name="target_name").exists())

    def test_slug_from_name(self):
        role = MetadataRole.objects.create(name="Watch Time")
        self.assertEqual((role.slug, str(role)), ("watch-time", "Watch Time"))

    def test_name_without_slug(self):
        with self.assertRaises(ValidationError):
            ObjectType.objects.create(name="…")


class RepresentationTests(TestCase):
    def setUp(self):
        self.user = ActorType.objects.get(slug="user")
        self.person = ObjectType.objects.get(slug="person")
        self.video = ObjectType.objects.get(slug="video")
        self.collection = ObjectType.objects.get(slug="collection")
        self.view = ActivityType.objects.get(slug="viewed")
        self.add = ActivityType.objects.get(slug="added")
        platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.item = Annotation.objects.create(platform=platform, name="watch_history item")
        self.date = Annotation.objects.create(platform=platform, name="Date")
        self.when = MetadataRole.objects.get(slug="when")

    def activity(self, **fields):
        defaults = {
            "name": "Watched video",
            "actor": self.user,
            "activity": self.view,
            "object": self.video,
        }
        return Representation.objects.create(pattern=Pattern.ACTIVITY, **(defaults | fields))

    def test_fields_match_pattern(self):
        watched = self.activity()
        Representation.objects.create(pattern=Pattern.OBJECT, name="Video", object=self.video)
        Representation.objects.create(pattern=Pattern.UNMAPPED, name="Unclear")
        self.assertEqual(str(watched), "Watched video")
        # where a term is used, per slot
        self.assertEqual([r.name for r in self.video.as_object.all()], ["Video", "Watched video"])
        self.assertEqual(list(self.user.as_actor.all()), [watched])
        self.assertEqual(list(self.view.representations.all()), [watched])
        self.assertEqual(list(self.person.as_target.all()), [])
        invalid: list[dict[str, object]] = [
            {"pattern": Pattern.ACTIVITY, "actor": self.user, "object": self.video},
            {"pattern": Pattern.OBJECT, "object": self.video, "activity": self.view},
            {"pattern": Pattern.OBJECT},
            {"pattern": Pattern.UNMAPPED, "target": self.collection},
        ]
        for fields in invalid:
            with (
                self.subTest(fields=fields),
                transaction.atomic(),
                self.assertRaises(IntegrityError),
            ):
                Representation.objects.create(name="x", **fields)

    def test_describe(self):
        watched = self.activity()
        watched.annotations.add(self.item)
        link = describe(watched, self.date, self.when, Subject.ACTIVITY)
        self.assertEqual(str(link), "Watched video · when/activity: Date")
        self.assertEqual(list(self.date.metadata_links.all()), [link])
        self.assertEqual(list(self.item.representations.all()), [watched])
        with self.assertRaises(ValidationError):  # the same link twice
            describe(watched, self.date, self.when, Subject.ACTIVITY)

    def test_subject_must_be_a_filled_slot(self):
        name = MetadataRole.objects.get(slug="name")
        follow = ActivityType.objects.get(slug="followed")
        # a followers list: someone else follows the account owner, the username is the actor's
        other_user = ActorType.objects.get(slug="other-user")
        follower = self.activity(
            name="Follower", actor=other_user, activity=follow, object=self.person
        )
        added = self.activity(name="Added to playlist", activity=self.add, target=self.collection)
        for subject in Subject:
            with self.subTest(subject=subject):
                describe(added, self.date, name, subject)
        describe(follower, self.item, name, Subject.ACTOR)
        video = Representation.objects.create(
            pattern=Pattern.OBJECT, name="Video", object=self.video
        )
        describe(video, self.date, self.when, Subject.OBJECT)
        unclear = Representation.objects.create(pattern=Pattern.UNMAPPED, name="Unclear")
        rejected = [
            (follower, Subject.TARGET, "no target"),
            (video, Subject.ACTIVITY, "no activity"),
            (video, Subject.ACTOR, "no actor"),
            *((unclear, subject, f"no {subject}") for subject in Subject),
        ]
        for representation, subject, message in rejected:
            with (
                self.subTest(representation=representation.name, subject=subject),
                self.assertRaisesMessage(ValidationError, message),
            ):
                describe(representation, self.date, self.when, subject)

    def test_slots_in_use_are_kept(self):
        added = self.activity(name="Added to playlist", activity=self.add, target=self.collection)
        added.full_clean()
        link = describe(added, self.date, MetadataRole.objects.get(slug="name"), Subject.TARGET)
        added.target = None
        with self.assertRaisesMessage(ValidationError, "1 metadata link describe the target"):
            added.full_clean()
        link.delete()
        added.full_clean()


class AdminTests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_superuser("curator")
        self.client.force_login(self.curator)

    def test_vocabulary_creator_and_fixed_slug(self):
        url = reverse("admin:representations_objecttype_add")
        self.assertContains(self.client.get(url), 'name="slug"')
        self.client.post(url, {"name": "Playlist", "slug": "playlist", "description": ""})
        playlist = ObjectType.objects.get(slug="playlist")
        self.assertEqual(playlist.created_by, self.curator)
        change = reverse("admin:representations_objecttype_change", args=[playlist.pk])
        self.assertNotContains(self.client.get(change), 'name="slug"')
        self.client.post(change, {"name": "Play list", "slug": "other", "description": ""})
        playlist.refresh_from_db()
        self.assertEqual((playlist.name, playlist.slug), ("Play list", "playlist"))

    def test_representation_editor(self):
        response = self.client.post(
            reverse("admin:representations_representation_add"),
            {
                "pattern": Pattern.UNMAPPED,
                "name": "Unclear",
                "description": "",
                "note": "",
                "metadata_links-TOTAL_FORMS": "0",
                "metadata_links-INITIAL_FORMS": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Representation.objects.get(name="Unclear").updated_by, self.curator)
