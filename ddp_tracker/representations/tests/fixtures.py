"""A platform with a registered upload: a watch history (a list of objects) to represent."""

from ddp_tracker.core.tests.utils import parsed_upload
from ddp_tracker.ddps.models import Platform
from ddp_tracker.schemas.models import Location

HISTORY = "/a.json/history/[]"
MEMBERS = {
    "a.json": (
        b'{"history": [{"Date": "2024-01-01", "Link": "https://x.com/1", "Author": {"Name": "a"}}],'
        b' "tags": ["x"], "when": "2024"}'
    ),
}


class WatchHistory:
    """``self.item`` (the history's item) and its fields ``self.date``, ``self.link`` and
    ``self.author_name``; ``self.elsewhere`` (a value) and ``self.tag`` (a list's string item)
    are outside it."""

    platform: Platform

    def add_watch_history(self, platform: Platform) -> None:
        self.platform = platform
        parsed_upload(platform, MEMBERS, register=True)
        self.item = self.location(HISTORY)
        self.date = self.location(f"{HISTORY}/Date")
        self.link = self.location(f"{HISTORY}/Link")
        self.author_name = self.location(f"{HISTORY}/Author/Name")
        self.elsewhere = self.location("/a.json/when")
        self.tag = self.location("/a.json/tags/[]")

    def location(self, path: str) -> Location:
        return Location.objects.get(platform=self.platform, path=path)
