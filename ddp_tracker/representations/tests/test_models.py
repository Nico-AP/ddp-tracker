from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import parsed_file, parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.representations.eligibility import (
    can_have_representation,
    eligible,
    is_eligible,
    metadata_candidates,
)
from ddp_tracker.representations.forms import DataPointField
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
from ddp_tracker.representations.tests.fixtures import WatchHistory
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.profiles import Profile
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


class EligibilityTests(WatchHistory, TestCase):
    def setUp(self):
        self.add_watch_history(Platform.objects.create(name="TikTok", slug="tiktok"))

    def test_a_list_items_that_are_objects(self):
        locations = Location.objects.filter(platform=self.platform)
        self.assertEqual(eligible(locations), {self.item.pk})
        self.assertTrue(is_eligible(self.item))
        for location in (self.date, self.elsewhere, self.tag, self.location("/a.json/history")):
            with self.subTest(path=location.path):
                self.assertFalse(is_eligible(location))

    def test_by_the_main_type(self):
        profile = Profile(path="/x/[]")
        profile.types.update({"object": 2, "null|object": 1})
        item = Location(path="/x/[]")
        self.assertTrue(can_have_representation(item, profile))
        profile.types.update({"string": 5})
        self.assertFalse(can_have_representation(item, profile))

    def test_metadata_candidates_are_the_data_points_below(self):
        paths = [location.path for location in metadata_candidates(self.item)]
        self.assertEqual(paths, [self.author_name.path, self.date.path, self.link.path])
        self.link.ignored = True
        self.link.save()
        self.assertNotIn(self.link, metadata_candidates(self.item))

    def test_data_points_are_labelled_from_the_list_on(self):
        self.date.annotation = Annotation.objects.create(platform=self.platform, name="Date")
        self.date.save()
        parsed_upload(self.platform, {"list.json": b'[{"id": 1}]'}, register=True)
        parsed_file(self.platform, "posts.csv", b"id\n1\n", register=True)
        cases = [
            (self.item, ["history/[]/Author/Name", "history/[]/Date (Date)", "history/[]/Link"]),
            (self.location("/list.json/[]"), ["list.json/[]/id"]),  # a file that is a list
            (self.location("/[]"), ["[]/id"]),  # a CSV: its rows are the root's items
        ]
        for anchor, labels in cases:
            with self.subTest(anchor=anchor.path):
                field = DataPointField(queryset=Location.objects.none())
                field.offer(anchor)
                shown = metadata_candidates(anchor)
                offered = [field.label_from_instance(location) for location in shown]
                self.assertEqual(offered, labels)


class RepresentationTests(WatchHistory, TestCase):
    def setUp(self):
        self.user = ActorType.objects.get(slug="user")
        self.person = ObjectType.objects.get(slug="person")
        self.video = ObjectType.objects.get(slug="video")
        self.collection = ObjectType.objects.get(slug="collection")
        self.view = ActivityType.objects.get(slug="viewed")
        self.add = ActivityType.objects.get(slug="added")
        self.add_watch_history(Platform.objects.create(name="TikTok", slug="tiktok"))
        self.when = MetadataRole.objects.get(slug="when")

    def activity(self, **fields):
        defaults = {
            "name": "Watched video",
            "actor": self.user,
            "activity": self.view,
            "object": self.video,
        }
        return Representation.objects.create(
            location=self.item, pattern=Pattern.ACTIVITY, **(defaults | fields)
        )

    def create(self, **fields):
        return Representation.objects.create(location=self.item, **fields)

    def test_fields_match_pattern(self):
        watched = self.activity()
        self.create(pattern=Pattern.OBJECT, name="Video", object=self.video)
        self.create(pattern=Pattern.UNMAPPED, name="Unclear")
        self.assertEqual(str(watched), "Watched video")
        self.assertEqual(self.item.representations.count(), 3)  # a location can have several
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
                self.create(name="x", **fields)

    def test_describe(self):
        watched = self.activity()
        link = describe(watched, self.date, self.when, Subject.ACTIVITY)
        self.assertEqual(str(link), f"Watched video · when/activity: TikTok: {self.date.path}")
        self.assertEqual(list(self.date.metadata_links.all()), [link])
        self.assertEqual(link.relative_path, "Date")
        nested = describe(watched, self.author_name, self.when, Subject.OBJECT)
        self.assertEqual(nested.relative_path, "Author/Name")
        with self.assertRaises(ValidationError):  # the same link twice
            describe(watched, self.date, self.when, Subject.ACTIVITY)

    def test_only_locations_below_describe(self):
        watched = self.activity()
        other = Platform.objects.create(name="YouTube", slug="youtube")
        elsewhere = Location.objects.create(platform=other, path=self.date.path)
        for location in (self.elsewhere, self.item, elsewhere):
            with (
                self.subTest(location=str(location)),
                self.assertRaisesMessage(ValidationError, "below the representation's location"),
            ):
                describe(watched, location, self.when, Subject.ACTIVITY)

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
        describe(follower, self.author_name, name, Subject.ACTOR)
        video = self.create(pattern=Pattern.OBJECT, name="Video", object=self.video)
        describe(video, self.date, self.when, Subject.OBJECT)
        unclear = self.create(pattern=Pattern.UNMAPPED, name="Unclear")
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
        location = Location.objects.create(
            platform=Platform.objects.create(name="TikTok", slug="tiktok"), path="/[]"
        )
        response = self.client.post(
            reverse("admin:representations_representation_add"),
            {
                "location": location.pk,
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
