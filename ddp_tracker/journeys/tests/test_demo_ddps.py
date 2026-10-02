"""The fictional packages that seed_demo uploads (demo/ddps.py): the same on every run, and
parsed by the real parser into the paths the demo data relies on."""

import hashlib
import io
import json
import re
import zipfile

from django.test import SimpleTestCase

from ddp_parser import parse, walk
from ddp_tracker.journeys.demo import ddps

T = "/user_data_tiktok.json"
BUILDERS = (ddps.tiktok, ddps.tiktok_march, ddps.instagram, ddps.facebook, ddps.youtube)
LIKE_DATE = f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date"


def paths(files, name="export.zip"):
    """The paths the parser makes of a package."""
    return {node.path for node in walk(parse(ddps.build_zip(files), name=name).root)}


class BuildZipTests(SimpleTestCase):
    def test_a_package_is_the_same_on_every_run(self):
        for build in BUILDERS:
            with self.subTest(package=build.__name__):
                first = hashlib.sha256(ddps.build_zip(build())).hexdigest()
                self.assertEqual(hashlib.sha256(ddps.build_zip(build())).hexdigest(), first)

    def test_building_other_packages_in_between_changes_nothing(self):
        alone = ddps.build_zip(ddps.instagram())
        ddps.tiktok()
        ddps.facebook()
        self.assertEqual(ddps.build_zip(ddps.instagram()), alone)

    def test_members_are_written_by_their_kind(self):
        data = ddps.build_zip({"a.csv": "x,y\n1,2\n", "b.bin": b"\x00\x01", "c.json": {"k": 1}})
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.read("a.csv"), b"x,y\n1,2\n")
            self.assertEqual(archive.read("b.bin"), b"\x00\x01")
            self.assertEqual(json.loads(archive.read("c.json")), {"k": 1})


class PackageTests(SimpleTestCase):
    def test_tiktok_september(self):
        found = paths(ddps.tiktok())
        for path in (
            f"{T}/Your Activity/Watch History/VideoList/[]/Date",
            f"{T}/Your Activity/Searches/SearchList/[]/SearchTerm",
            LIKE_DATE,
            f"{T}/Direct Message/Direct Messages/ChatHistory/Chat History with {{*}}/[]/Content",
            f"{T}/Tiktok Live/Go Live History/GoLiveList",
        ):
            self.assertIn(path, found)
        self.assertNotIn(f"{T}/Activity", found)

    def test_tiktok_march_is_the_older_shape(self):
        files = ddps.tiktok_march()
        document = parse(ddps.build_zip(files), name="export.zip")
        formats = {node.path: getattr(node, "format", None) for node in walk(document.root)}
        self.assertIn(f"{T}/Activity/Video Browsing History/VideoList/[]/Date", formats)
        self.assertIn(f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived", formats)
        self.assertNotIn(f"{T}/Your Activity", formats)
        self.assertFalse([path for path in formats if "Tiktok Live" in path])
        self.assertEqual(formats[LIKE_DATE], "%Y-%m-%dT%H:%M:%SZ")
        # its values are from before its own request date
        likes = files[ddps.TIKTOK_FILE]["Likes and Favorites"]["Like List"]["ItemFavoriteList"]
        self.assertLess(max(like["date"] for like in likes), "2026-03-16")

    def test_the_september_like_dates_have_no_time_zone_marker(self):
        document = parse(ddps.build_zip(ddps.tiktok()), name="export.zip")
        formats = {node.path: getattr(node, "format", None) for node in walk(document.root)}
        self.assertEqual(formats[LIKE_DATE], "%Y-%m-%d %H:%M:%S")

    def test_instagram(self):
        found = paths(ddps.instagram())
        for path in (
            "/your_instagram_activity/likes/liked_posts.json/[]/timestamp",
            "/your_instagram_activity/messages/inbox/{*}/message_1.json/messages/[]/content",
            "/connections/followers_and_following/following.json/relationships_following/[]/title",
            # the four stories all fall in September 2026, so the month folder stays as it is
            "/media/stories/202609/{*}.jpg",
        ):
            self.assertIn(path, found)

    def test_facebook_loses_its_wrapper_folder(self):
        found = paths(ddps.facebook(), name="facebook-noorfictional-2026-09-15-AbCdEf12.zip")
        for path in (
            "/your_facebook_activity/comments_and_reactions/comments.json/comments_v2/[]/timestamp",
            "/logged_information/search/your_search_history.json/searches_v2/[]/data/[]/text",
            "/security_and_login_information/logins_and_logouts.json/{*}/[]/ip_address",
        ):
            self.assertIn(path, found)
        self.assertFalse([path for path in found if path.startswith("/facebook-")])

    def test_youtube(self):
        found = paths(ddps.youtube())
        root = "/Takeout/YouTube and YouTube Music"
        for path in (
            f"{root}/history/watch-history.json/[]/time",
            f"{root}/history/search-history.json/[]/title",
            f"{root}/subscriptions/subscriptions.csv/[]/Channel Title",
        ):
            self.assertIn(path, found)

    def test_every_e_mail_address_is_fictional(self):
        for build in BUILDERS:
            text = json.dumps(
                {name: data for name, data in build().items() if not isinstance(data, bytes)}
            )
            for address in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
                self.assertTrue(address.endswith("@example.org"), address)
