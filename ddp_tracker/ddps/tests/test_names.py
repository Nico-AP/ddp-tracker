from django.test import SimpleTestCase

from ddp_tracker.ddps.names import anonymize_file_name


class AnonymizeFileNameTests(SimpleTestCase):
    def test_examples(self):
        for name, expected in (
            ("TikTok_Data_johndoe_2024-05-01 (1).zip", "TikTok_Data_xxxxxxx_0000-00-00 (0).zip"),
            ("instagram-anna.smith-20240501.zip", "instagram-xxxx.xxxxx-00000000.zip"),
            ("user_data_tiktok.json", "user_data_tiktok.json"),  # only whitelisted words
            ("MY DATA.CSV", "MY DATA.CSV"),  # any case
            ("Zoë_Müller.json", "xxx_xxxxxx.json"),  # accented letters are letters
            ("userData42.json", "xxxxxxxx00.json"),  # whole runs only: no camelCase split
            ("C:\\Users\\anna\\export.zip", "export.zip"),  # a browser's full path
            ("/home/anna/export.zip", "export.zip"),
        ):
            with self.subTest(name=name):
                self.assertEqual(anonymize_file_name(name), expected)

    def test_is_idempotent(self):
        once = anonymize_file_name("facebook-johndoe_1234.zip")
        self.assertEqual(anonymize_file_name(once), once)
