import io
import json
import tempfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from ddp_parser import from_dict, walk
from ddp_tracker.annotations.models import Annotation
from ddp_tracker.core.tests.utils import make_zip, parsed_upload
from ddp_tracker.ddps.models import PathRule, Platform, Upload
from ddp_tracker.ddps.rules import options_for
from ddp_tracker.ddps.tasks import parse_upload
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.representations.models import (
    MetadataRole,
    Pattern,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.schemas.models import Location
from ddp_tracker.schemas.renormalize import renormalize
from ddp_tracker.schemas.services import register_upload
from ddp_tracker.users.models import User

FILE = "/user_data_tiktok.json"
CHATS = f"{FILE}/ChatHistory"
RULE = f"{CHATS}/Chat History with *"
NEW = f"{CHATS}/Chat History with {{*}}"


def chats(partner: str) -> dict[str, bytes]:
    messages = [{"Date": "2026-01-02 10:00:00", "Content": "hi"}]
    data = {"ChatHistory": {f"Chat History with {partner}": messages}}
    return {"user_data_tiktok.json": json.dumps(data).encode()}


class RenormalizeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("curator")
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        self.anna = parsed_upload(self.platform, chats("anna"), register=True)
        self.tom = parsed_upload(self.platform, chats("tom"), register=True)

    def location(self, path: str) -> Location:
        return Location.objects.get(platform=self.platform, path=path)

    def add_rule(self):
        PathRule.objects.create(platform=self.platform, pattern=RULE)

    def test_paths_are_renamed_and_uploads_re_registered(self):
        self.add_rule()
        report = renormalize(self.platform)
        self.assertEqual((report.uploads, report.conflicts), (2, []))
        self.assertIn(f"{NEW}/[]/Content", report.paths)
        paths = set(self.platform.locations.values_list("path", flat=True))
        self.assertIn(f"{NEW}/[]/Content", paths)
        self.assertFalse([path for path in paths if "anna" in path or "tom" in path])
        for upload in (self.anna, self.tom):
            upload.refresh_from_db()
            assert upload.document is not None
            self.assertIsNotNone(upload.registered_at)
            document = from_dict(upload.document)
            self.assertIn(NEW, {node.path for node in walk(document.root)})
            self.assertEqual(document.options["variable_keys"], [RULE])
            self.assertTrue(upload.observations.filter(location__path=NEW).exists())
        self.assertEqual(self.location(NEW).observations.count(), 2)

    def test_curation_moves_to_the_new_location(self):
        content = self.location(f"{CHATS}/Chat History with anna/[]/Content")
        item = self.location(f"{CHATS}/Chat History with anna/[]")
        message = Annotation.objects.create(platform=self.platform, name="Message")
        content.annotation = message
        content.example_values = [{"value": "hello", "source": "user_input"}]
        content.save()
        other = self.location(f"{CHATS}/Chat History with tom/[]/Content")
        other.annotation = Annotation.objects.create(platform=self.platform, name="Text")
        other.save()
        Location.objects.filter(path=f"{CHATS}/Chat History with tom/[]/Date").update(ignored=True)
        representation = Representation.objects.create(
            location=item, pattern=Pattern.UNMAPPED, name="Chat message"
        )
        link = RepresentationMetadata.objects.create(
            representation=representation,
            location=content,
            role=MetadataRole.objects.get(slug="when"),
            subject=RepresentationMetadata.Subject.OBJECT,
        )
        proposal = Proposal.objects.create(
            kind=Proposal.Kind.NEW_ANNOTATION,
            proposed_by=self.user,
            platform=self.platform,
            location=item,
            values={"name": "Chat", "also": [content.pk, other.pk]},
            base={"metadata": [{"subject": "object", "role": 1, "location": content.pk}]},
        )
        self.add_rule()
        report = renormalize(self.platform)

        new_content = self.location(f"{NEW}/[]/Content")
        new_item = self.location(f"{NEW}/[]")
        self.assertEqual(new_content.annotation, message)
        self.assertEqual(new_content.example_values, [{"value": "hello", "source": "user_input"}])
        self.assertTrue(self.location(f"{NEW}/[]/Date").ignored)
        self.assertEqual(len(report.conflicts), 1)
        self.assertIn("“Message”", report.conflicts[0])
        representation.refresh_from_db()
        link.refresh_from_db()
        proposal.refresh_from_db()
        self.assertEqual(representation.location, new_item)
        self.assertEqual(link.location, new_content)
        self.assertEqual(proposal.location, new_item)
        self.assertEqual(proposal.values["also"], [new_content.pk])
        self.assertEqual(proposal.base["metadata"][0]["location"], new_content.pk)
        self.assertFalse(Location.objects.filter(path__contains="anna").exists())
        self.assertEqual(report.moved, 8)  # the chat, its item, Date and Content, twice

    def test_duplicate_metadata_links_are_dropped(self):
        role = MetadataRole.objects.get(slug="when")
        representation = Representation.objects.create(
            location=self.location(f"{CHATS}"), pattern=Pattern.UNMAPPED, name="Chats"
        )
        for partner in ("anna", "tom"):
            RepresentationMetadata.objects.create(
                representation=representation,
                location=self.location(f"{CHATS}/Chat History with {partner}/[]/Date"),
                role=role,
                subject=RepresentationMetadata.Subject.OBJECT,
            )
        self.add_rule()
        renormalize(self.platform)
        self.assertEqual(
            list(representation.metadata_links.values_list("location__path", flat=True)),
            [f"{NEW}/[]/Date"],
        )

    def test_twice_and_without_rules_changes_nothing(self):
        self.assertEqual(renormalize(self.platform).uploads, 0)
        self.add_rule()
        renormalize(self.platform)
        self.assertEqual(renormalize(self.platform).uploads, 0)

    def test_dry_run(self):
        self.add_rule()
        report = renormalize(self.platform, dry_run=True)
        self.assertEqual(report.uploads, 2)
        self.assertIn(NEW, report.paths)
        self.assertTrue(self.location(f"{CHATS}/Chat History with anna").pk)
        self.anna.refresh_from_db()
        assert self.anna.document is not None
        self.assertNotIn("{*}", json.dumps(self.anna.document))

    def test_unregistered_uploads_only_get_their_document_renamed(self):
        held = parsed_upload(self.platform, chats("eve"))
        self.add_rule()
        renormalize(self.platform)
        held.refresh_from_db()
        assert held.document is not None
        self.assertIn("Chat History with {*}", json.dumps(held.document))
        self.assertIsNone(held.registered_at)
        self.assertFalse(held.observations.exists())

    def test_wrapper_folder_of_a_stored_upload(self):
        wrapped = parsed_upload(self.platform, {"export-anna/data.json": b'{"a": 1}'})
        assert wrapped.document is not None
        wrapped.document["root"]["name"] = "export-anna.zip"  # as if uploaded under that name
        wrapped.save()
        register_upload(wrapped)
        self.assertTrue(self.location("/export-anna/data.json/a"))
        renormalize(self.platform)
        self.assertTrue(self.location("/data.json/a"))
        self.assertFalse(Location.objects.filter(path__startswith="/export-anna").exists())


class RulesTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")

    def test_options_for(self):
        PathRule.objects.create(platform=self.platform, pattern=RULE)
        PathRule.objects.create(
            platform=self.platform, kind=PathRule.Kind.KEEP_KEY, pattern=f"{CHATS}/x"
        )
        other = Platform.objects.create(name="Instagram", slug="instagram")
        PathRule.objects.create(platform=other, pattern="/other/*")
        options = options_for(self.platform, samples=True)
        self.assertEqual(
            (options.variable_keys, options.keep_keys, options.samples),
            ((RULE,), (f"{CHATS}/x",), True),
        )
        self.assertEqual(
            str(PathRule.objects.get(pattern=RULE)),
            f"TikTok: Variable key: rename matching keys {RULE}",
        )

    def test_new_uploads_are_parsed_with_the_rules(self):
        PathRule.objects.create(platform=self.platform, pattern=RULE)
        upload = Upload.objects.create(
            platform=self.platform, requested_at="2026-09-01", file_name="export.zip"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x"
            path.write_bytes(make_zip(chats("anna")))
            parse_upload.call(upload.pk, str(path))
        upload.refresh_from_db()
        document = json.dumps(upload.document)
        self.assertIn("Chat History with {*}", document)
        self.assertNotIn("anna", document)


class AdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser("staff")
        self.client.force_login(self.staff)
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(self.platform, chats("anna"), register=True)

    def test_saving_a_rule_renormalizes_the_platform(self):
        data = {"platform": self.platform.pk, "kind": "variable_key", "pattern": RULE}
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(reverse("admin:ddps_pathrule_add"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(PathRule.objects.get().created_by, self.staff)
        self.assertTrue(Location.objects.filter(path=NEW).exists())
        self.assertFalse(Location.objects.filter(path__contains="anna").exists())

    def test_moving_a_rule_renormalizes_both_platforms(self):
        rule = PathRule.objects.create(platform=self.platform, pattern=RULE)
        other = Platform.objects.create(name="Instagram", slug="instagram")
        data = {"platform": other.pk, "kind": "variable_key", "pattern": RULE}
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.client.post(reverse("admin:ddps_pathrule_change", args=[rule.pk]), data)
        self.assertEqual(len(callbacks), 2)

    @override_settings(MESSAGE_STORAGE="django.contrib.messages.storage.cookie.CookieStorage")
    def test_deleting_a_rule_warns_that_renames_stay(self):
        rule = PathRule.objects.create(platform=self.platform, pattern=RULE)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse("admin:ddps_pathrule_delete", args=[rule.pk]), {"post": "yes"}, follow=True
            )
        self.assertEqual(callbacks, [])
        self.assertContains(response, "keep their renamed paths")
        other = PathRule.objects.create(platform=self.platform, pattern="/x/*")
        response = self.client.post(
            reverse("admin:ddps_pathrule_changelist"),
            {"action": "delete_selected", "_selected_action": [other.pk], "post": "yes"},
            follow=True,
        )
        self.assertContains(response, "keep their renamed paths")


class CommandTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="TikTok", slug="tiktok")
        parsed_upload(self.platform, chats("anna"), register=True)
        PathRule.objects.create(platform=self.platform, pattern=RULE)

    def test_dry_run_prints_new_paths_only(self):
        out = io.StringIO()
        call_command("renormalize", "--platform", "tiktok", "--dry-run", stdout=out)
        self.assertIn("would change 1 upload(s)", out.getvalue())
        self.assertIn(NEW, out.getvalue())
        self.assertNotIn("anna", out.getvalue())
        self.assertTrue(Location.objects.filter(path__contains="anna").exists())

    def test_run(self):
        out = io.StringIO()
        call_command("renormalize", stdout=out)
        self.assertIn("TikTok: changed 1 upload(s)", out.getvalue())
        self.assertFalse(Location.objects.filter(path__contains="anna").exists())

    def test_conflicts_are_printed(self):
        other = parsed_upload(self.platform, chats("tom"), register=True)
        for partner, name in (("anna", "Message"), ("tom", "Text")):
            Location.objects.filter(path=f"{CHATS}/Chat History with {partner}/[]/Content").update(
                annotation=Annotation.objects.create(platform=self.platform, name=name)
            )
        out = io.StringIO()
        call_command("renormalize", stdout=out)
        self.assertIn("conflict:", out.getvalue())
        self.assertTrue(other.observations.exists())

    def test_unknown_platform(self):
        with self.assertRaisesMessage(CommandError, "no platform 'nope'"):
            call_command("renormalize", "--platform", "nope")
