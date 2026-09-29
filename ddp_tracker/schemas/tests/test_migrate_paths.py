from django.test import TestCase

from ddp_parser import redact_document_paths, redact_path
from ddp_tracker.schemas.migrate_paths import _migrated_name
from ddp_tracker.schemas.models import Location


class MigratePathsTests(TestCase):
    def test_migrated_name_keeps_collapsed_mask(self):
        location = Location(name="xs0", path="/messages/inbox/{*}")
        self.assertEqual(
            _migrated_name(location, "/messages/inbox/{*}", "/messages/inbox/{*}"),
            "xs0",
        )

    def test_redact_document_paths_updates_nodes(self):
        document = {
            "root": {
                "kind": "file",
                "path": "/messages/inbox/alice_123456789012345/x.json",
                "properties": {},
            }
        }
        redact_document_paths(document)
        path = document["root"]["path"]
        self.assertNotIn("alice_123456789012345", path)
        self.assertEqual(path, redact_path("/messages/inbox/alice_123456789012345/x.json"))
