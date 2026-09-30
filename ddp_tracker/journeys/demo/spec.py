"""What ``seed_demo`` creates: two users, four platforms, five uploads, and the curation on top
(annotations, representations, example values, one suggestion). All of it is fictional: the
persona "Noor Vermeulen" and everything around her is made up (``ddps.py``).

The paths are what the parser makes of the fictional packages. ``seed.py`` stops with an error
if one of them does not exist, so a change in the parser or the packages shows up at once.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ddp_tracker.journeys.demo import ddps

# --- users ------------------------------------------------------------------------------------

ADMIN, CURATOR = "admin", "curator"
ADMIN_EMAIL = "demo-admin@example.org"  # staff and superuser
CURATOR_EMAIL = "demo-curator@example.org"  # not staff: uploads and suggests
# the password of both, when DEBUG is on (seed_demo makes a random one otherwise)
DEMO_PASSWORD = "noor-demo-2026"  # noqa: S105 - a local demo login, never used without DEBUG

# --- platforms --------------------------------------------------------------------------------

PLATFORMS: tuple[tuple[str, str], ...] = (
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
)

# --- uploads ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class UploadSpec:
    platform: str  # slug
    file_name: str  # as the platform names it; stored anonymised, like any upload's
    requested_at: date
    build: Callable[[], dict[str, Any]]
    uploader: str = ADMIN
    hold: bool = False  # leave it waiting for approval, for the approvals queue


# In this order: the March TikTok package first, so that the September one has something to
# differ from. The first upload of a platform waits for approval, which the demo admin gives.
UPLOADS: tuple[UploadSpec, ...] = (
    UploadSpec("tiktok", "tiktok_fictional_2026-03-15.zip", date(2026, 3, 15), ddps.tiktok_march),
    UploadSpec("tiktok", "tiktok_fictional_2026-09-15.zip", date(2026, 9, 15), ddps.tiktok),
    UploadSpec(
        "instagram",
        "instagram-noor.fictional-2026-09-15-XyZ12345.zip",
        date(2026, 9, 15),
        ddps.instagram,
    ),
    UploadSpec(
        "facebook",
        "facebook-noorfictional-2026-09-15-AbCdEf12.zip",
        date(2026, 9, 15),
        ddps.facebook,
    ),
    UploadSpec(
        "youtube",
        "takeout-20260915T103000Z-001.zip",
        date(2026, 9, 15),
        ddps.youtube,
        uploader=CURATOR,
        hold=True,
    ),
)

# --- annotations ------------------------------------------------------------------------------

T = "/user_data_tiktok.json"
IG_ACTIVITY = "/your_instagram_activity"
IG_LOGIN = "/security_and_login_information/login_and_profile_creation"
FB_ACTIVITY = "/your_facebook_activity"


@dataclass(frozen=True)
class AnnotationSpec:
    platform: str
    name: str
    paths: tuple[str, ...]  # several: the same data point at another path (moved, renamed)
    description: str
    pii: bool = False
    note: str = ""


ANNOTATIONS: tuple[AnnotationSpec, ...] = (
    # TikTok
    AnnotationSpec(
        "tiktok",
        "Watched video",
        (
            f"{T}/Your Activity/Watch History/VideoList/[]",
            f"{T}/Activity/Video Browsing History/VideoList/[]",
        ),
        "One video that was shown to the user, with when it was watched and a link to the video.",
        note=(
            "Until spring 2026 the list was called Video Browsing History, in a section "
            "called Activity."
        ),
    ),
    AnnotationSpec(
        "tiktok",
        "Search",
        (f"{T}/Your Activity/Searches/SearchList/[]",),
        "One search the user made in the app, with when and the search term.",
    ),
    AnnotationSpec(
        "tiktok",
        "Search term",
        (f"{T}/Your Activity/Searches/SearchList/[]/SearchTerm",),
        "The text the user typed into the search field.",
        note="Free text: it can reveal interests, so treat it as sensitive.",
    ),
    AnnotationSpec(
        "tiktok",
        "Liked video",
        (f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]",),
        "One video the user liked, with when and a link to the video.",
    ),
    AnnotationSpec(
        "tiktok",
        "Login",
        (f"{T}/Your Activity/Login History/LoginHistoryList/[]",),
        "One login to the account, with the device, the network and the IP address.",
    ),
    AnnotationSpec(
        "tiktok",
        "Login IP address",
        (f"{T}/Your Activity/Login History/LoginHistoryList/[]/IP",),
        "The IP address the user logged in from.",
        pii=True,
    ),
    AnnotationSpec(
        "tiktok",
        "Off-platform activity event",
        (f"{T}/Ads and data/Off TikTok Activity/OffTikTokActivityDataList/[]",),
        (
            "Something the user did outside TikTok that another company reported to TikTok, "
            "for example viewing a page in a web shop."
        ),
        note=(
            "What happened is in the field Event. Its values may need different "
            "representations (raised at the hackathon)."
        ),
    ),
    AnnotationSpec(
        "tiktok",
        "Direct message text",
        (f"{T}/Direct Message/Direct Messages/ChatHistory/Chat History with {{*}}/[]/Content",),
        "The text of one direct message, sent or received.",
        pii=True,
    ),
    AnnotationSpec(
        "tiktok",
        "Account e-mail address",
        (f"{T}/Profile And Settings/Profile Info/ProfileMap/emailAddress",),
        "The e-mail address registered for the account.",
        pii=True,
    ),
    AnnotationSpec(
        "tiktok",
        "Comment written",
        (f"{T}/Comment/Comments/CommentsList/[]",),
        "One comment the user wrote under a video, with when.",
        note="Fields without a value hold the marker N/A, not an empty value.",
    ),
    AnnotationSpec(
        "tiktok",
        "Account followed",
        (f"{T}/Profile And Settings/Following/Following/[]",),
        "One account the user follows, with since when.",
    ),
    AnnotationSpec(
        "tiktok",
        "Likes received",
        (f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived",),
        "How many likes the user's own videos received in total?",
        note="Last seen in the package requested in March 2026.",
    ),
    # Instagram
    AnnotationSpec(
        "instagram",
        "Liked post",
        (f"{IG_ACTIVITY}/likes/liked_posts.json/[]",),
        "One post the user liked, with when, a link to the post and its owner.",
    ),
    AnnotationSpec(
        "instagram",
        "Keyword search",
        ("/logged_information/recent_searches/word_or_phrase_searches.json/searches_keyword/[]",),
        "One word or phrase the user searched for, with when.",
    ),
    AnnotationSpec(
        "instagram",
        "Direct message text",
        (f"{IG_ACTIVITY}/messages/inbox/{{*}}/message_1.json/messages/[]/content",),
        "The text of one direct message, sent or received.",
        pii=True,
    ),
    AnnotationSpec(
        "instagram",
        "Ad viewed",
        ("/ads_information/ads_and_topics/ads_viewed.json/[]",),
        "One ad that was shown to the user, with when and the advertiser.",
    ),
    AnnotationSpec(
        "instagram",
        "Account followed",
        ("/connections/followers_and_following/following.json/relationships_following/[]",),
        "One account the user follows, with since when.",
    ),
    AnnotationSpec(
        "instagram",
        "Video watched",
        ("/ads_information/ads_and_topics/videos_watched.json/[]",),
        "One video the user watched, with when and its author.",
    ),
    AnnotationSpec(
        "instagram",
        "Comment written",
        (f"{IG_ACTIVITY}/comments/post_comments_1.json/[]",),
        "One comment the user wrote under a post, with when and the owner of the post.",
    ),
    AnnotationSpec(
        "instagram",
        "Login",
        (f"{IG_LOGIN}/login_activity.json/account_history_login_history/[]",),
        "One login to the account, with the IP address, the language and the browser or app.",
        pii=True,
    ),
    # Facebook
    AnnotationSpec(
        "facebook",
        "Reaction to a post",
        (f"{FB_ACTIVITY}/comments_and_reactions/likes_and_reactions_1.json/[]",),
        "One reaction (like, love, haha and so on) the user gave, with when.",
    ),
    AnnotationSpec(
        "facebook",
        "Comment written",
        (f"{FB_ACTIVITY}/comments_and_reactions/comments.json/comments_v2/[]",),
        "One comment the user wrote, with when and its text.",
    ),
    AnnotationSpec(
        "facebook",
        "Search",
        ("/logged_information/search/your_search_history.json/searches_v2/[]",),
        "One search the user made on Facebook, with when and the search text.",
    ),
    AnnotationSpec(
        "facebook",
        "Off-Meta activity event",
        ("/apps_and_websites_off_of_facebook/your_activity_off_meta_technologies.json/[]",),
        "Something the user did in another company's app or website that was reported to Meta.",
    ),
    AnnotationSpec(
        "facebook",
        "Login or logout",
        ("/security_and_login_information/logins_and_logouts.json/{*}/[]",),
        "One login, logout or session update, with when, where and the IP address.",
        pii=True,
        note=(
            "The key above this list shows as {*}: the parser takes Facebook's key "
            "account_accesses_v2 for a variable key (a known issue)."
        ),
    ),
    AnnotationSpec(
        "facebook",
        "Video watched",
        ("/logged_information/interactions/recently_viewed.json/recently_viewed/[]/entries/[]",),
        "One recently viewed item, such as a video, with when.",
    ),
    AnnotationSpec(
        "facebook",
        "Direct message text",
        (f"{FB_ACTIVITY}/messages/inbox/{{*}}/message_1.json/messages/[]/content",),
        "The text of one direct message, sent or received.",
        pii=True,
    ),
    AnnotationSpec(
        "facebook",
        "Account followed",
        ("/connections/followers/who_you've_followed.json/following_v3/[]",),
        "One page or person the user follows, with since when.",
    ),
)

# --- representations ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetadataSpec:
    path: str  # below the list's item: "Date", "string_list_data/[]/timestamp"
    role: str  # a MetadataRole's slug
    subject: str  # the slot it describes: "activity" or "object"


@dataclass(frozen=True)
class RepresentationSpec:
    platform: str
    path: str  # a list's item
    name: str
    actor: str  # vocabulary slugs
    activity: str
    object_type: str
    metadata: tuple[MetadataSpec, ...]
    note: str = ""


# "Liked" is not in the vocabulary: likes and reactions use "responded" (a like is a response),
# and the demo curator suggests the term (SUGGESTED_TERM), which stays unapproved.
LIKED_NOTE = (
    "A like is recorded with the activity responded. A term of its own, liked, has been suggested."
)

REPRESENTATIONS: tuple[RepresentationSpec, ...] = (
    RepresentationSpec(
        "tiktok",
        f"{T}/Your Activity/Watch History/VideoList/[]",
        "Watched a video",
        "user",
        "viewed",
        "video",
        (MetadataSpec("Date", "when", "activity"), MetadataSpec("Link", "identifier", "object")),
    ),
    RepresentationSpec(
        "tiktok",
        f"{T}/Your Activity/Searches/SearchList/[]",
        "Searched",
        "user",
        "searched",
        "object",
        (MetadataSpec("Date", "when", "activity"), MetadataSpec("SearchTerm", "value", "object")),
    ),
    RepresentationSpec(
        "tiktok",
        f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]",
        "Liked a video",
        "user",
        "responded",
        "video",
        (MetadataSpec("date", "when", "activity"), MetadataSpec("link", "identifier", "object")),
        note=LIKED_NOTE,
    ),
    RepresentationSpec(
        "instagram",
        f"{IG_ACTIVITY}/likes/liked_posts.json/[]",
        "Liked a post",
        "user",
        "responded",
        "image",
        (MetadataSpec("timestamp", "when", "activity"),),
        note=LIKED_NOTE,
    ),
    RepresentationSpec(
        "instagram",
        "/connections/followers_and_following/following.json/relationships_following/[]",
        "Followed an account",
        "user",
        "followed",
        "profile",
        (
            MetadataSpec("title", "name", "object"),
            MetadataSpec("string_list_data/[]/timestamp", "when", "activity"),
        ),
    ),
    RepresentationSpec(
        "instagram",
        "/logged_information/recent_searches/word_or_phrase_searches.json/searches_keyword/[]",
        "Searched",
        "user",
        "searched",
        "object",
        (
            MetadataSpec("string_map_data/Search/value", "value", "object"),
            MetadataSpec("string_map_data/Time/timestamp", "when", "activity"),
        ),
    ),
    RepresentationSpec(
        "facebook",
        f"{FB_ACTIVITY}/comments_and_reactions/comments.json/comments_v2/[]",
        "Wrote a comment",
        "user",
        "created",
        "note",
        (
            MetadataSpec("timestamp", "when", "activity"),
            MetadataSpec("data/[]/comment/comment", "value", "object"),
        ),
    ),
    RepresentationSpec(
        "facebook",
        "/logged_information/search/your_search_history.json/searches_v2/[]",
        "Searched",
        "user",
        "searched",
        "object",
        (
            MetadataSpec("timestamp", "when", "activity"),
            MetadataSpec("data/[]/text", "value", "object"),
        ),
    ),
    RepresentationSpec(
        "facebook",
        f"{FB_ACTIVITY}/comments_and_reactions/likes_and_reactions_1.json/[]",
        "Reacted to a post",
        "user",
        "responded",
        "note",
        (
            MetadataSpec("timestamp", "when", "activity"),
            MetadataSpec("data/[]/reaction/reaction", "value", "activity"),
        ),
        note=LIKED_NOTE,
    ),
)

# --- example values (typed by a curator, all fictional) ------------------------------------


@dataclass(frozen=True)
class ExampleSpec:
    platform: str
    path: str
    examples: tuple[str, ...]


EXAMPLES: tuple[ExampleSpec, ...] = (
    ExampleSpec(
        "tiktok", f"{T}/Your Activity/Watch History/VideoList/[]/Date", ("2026-09-01 08:15:42",)
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Your Activity/Watch History/VideoList/[]/Link",
        ("https://www.tiktokv.com/share/video/7400000000000000001/",),
    ),
    ExampleSpec(
        "tiktok", f"{T}/Your Activity/Searches/SearchList/[]/Date", ("2026-08-30 21:03:10",)
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Your Activity/Searches/SearchList/[]/SearchTerm",
        ("utrecht cycling routes", "monstera care"),
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date",
        ("2026-09-02 19:44:05",),
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/link",
        ("https://www.tiktokv.com/share/video/7400000000000000002/",),
    ),
    ExampleSpec(
        "tiktok", f"{T}/Your Activity/Login History/LoginHistoryList/[]/IP", ("192.0.2.17",)
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Your Activity/Login History/LoginHistoryList/[]/DeviceModel",
        ("Pixel 8",),
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Ads and data/Off TikTok Activity/OffTikTokActivityDataList/[]/Event",
        ("Page View", "Add to Cart"),
    ),
    ExampleSpec(
        "tiktok",
        f"{T}/Ads and data/Off TikTok Activity/OffTikTokActivityDataList/[]/Source",
        ("GreenLeaf Plants BV",),
    ),
    ExampleSpec("tiktok", f"{T}/Comment/Comments/CommentsList/[]/photo", ("N/A",)),
    ExampleSpec(
        "tiktok",
        f"{T}/Comment/Comments/CommentsList/[]/date",
        ("2026-08-21 17:30:12",),
    ),
    ExampleSpec("instagram", f"{IG_ACTIVITY}/likes/liked_posts.json/[]/timestamp", ("1757930000",)),
    ExampleSpec(
        "instagram",
        "/logged_information/recent_searches/word_or_phrase_searches.json/searches_keyword/[]"
        "/string_map_data/Search/value",
        ("houseplant pests",),
    ),
    ExampleSpec(
        "instagram",
        "/connections/followers_and_following/following.json/relationships_following/[]/title",
        ("daan_jansen_fic",),
    ),
    ExampleSpec(
        "facebook",
        f"{FB_ACTIVITY}/comments_and_reactions/comments.json/comments_v2/[]/data/[]/comment/comment",
        ("Gefeliciteerd!",),
    ),
    ExampleSpec(
        "facebook",
        f"{FB_ACTIVITY}/comments_and_reactions/likes_and_reactions_1.json/[]/data/[]/reaction/reaction",
        ("LIKE", "LOVE"),
    ),
    ExampleSpec(
        "facebook",
        "/logged_information/search/your_search_history.json/searches_v2/[]/data/[]/text",
        ("dutch election polls",),
    ),
)

# --- what the demo curator (not staff) adds ------------------------------------------------

# a vocabulary term that waits for an administrator's approval: (name, description)
SUGGESTED_TERM = ("liked", "The actor liked the object.")

# an open suggestion in the staff's queue: a new annotation for a data point
SUGGESTION_PATH = f"{T}/Likes and Favorites/Favorite Videos/FavoriteVideoList/[]"
SUGGESTION_VALUES: dict[str, Any] = {
    "name": "Favourite video",
    "description": "One video the user saved to their favourites, with when.",
    "note": "",
    "pii": False,
}
SUGGESTION_COMMENT = "Seen in my own export. The list is separate from the likes."
