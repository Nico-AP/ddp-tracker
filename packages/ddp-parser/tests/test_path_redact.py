import unittest

from ddp_parser.privacy.path_redact import redact_path, redact_path_parts


class PathRedactTests(unittest.TestCase):
    def test_messages_thread_folder(self):
        parts = redact_path_parts(["messages", "inbox", "alice_123456789012345", "message_1.json"])
        self.assertEqual(parts[0], "messages")
        self.assertEqual(parts[1], "inbox")
        self.assertNotIn("alice_123456789012345", parts[2])
        self.assertTrue(parts[2].startswith("u"))

    def test_email_segment(self):
        self.assertEqual(
            redact_path("/exports/user@example.com/data.json"), "/exports/{email}/data.json"
        )

    def test_reserved_segments_unchanged(self):
        self.assertEqual(
            redact_path("/messages/inbox/{*}/message_{n}.json"),
            "/messages/inbox/{*}/message_{n}.json",
        )
        self.assertEqual(redact_path("/list.json/[]/field"), "/list.json/[]/field")
