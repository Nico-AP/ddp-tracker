from unittest import TestCase

import ddp_parser


class PackageTests(TestCase):
    def test_version_matches_distribution_metadata(self):
        self.assertEqual(ddp_parser.__version__, "0.1.0")
