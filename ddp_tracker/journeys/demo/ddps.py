"""Fictional data download packages (DDPs) for the demo data (``manage.py seed_demo``), built
in memory: no binary file and nothing that looks personal is kept in the repository.

Everything in them is invented: the persona "Noor Vermeulen", her friends, messages, searches
and IDs. E-mail addresses use example.org, IP addresses the ranges reserved for documentation
(RFC 5737). The structure (folders, file names, keys, value formats) follows what real
Facebook, Instagram, TikTok and YouTube exports looked like in 2026.
"""

import io
import json
import random
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

type Files = dict[str, Any]  # zip member name → bytes (as is), str (UTF-8 text), or JSON data

SEED = 20260930
SEPTEMBER = datetime(2026, 9, 15, 10, 30, tzinfo=UTC)
MARCH = datetime(2026, 3, 15, 10, 30, tzinfo=UTC)
TIKTOK_FILE = "user_data_tiktok.json"
TIKTOK_DATE = "%Y-%m-%d %H:%M:%S"

# How often something happens, for the random generator.
REACTION_CHANCE = 0.2  # an Instagram message has a reaction
SHARE_CHANCE = 0.15  # an Instagram message shares a post
EVEN_CHANCE = 0.5  # an advertiser has a custom audience; a Facebook post has a photo

PERSONA = {
    "first": "Noor",
    "last": "Vermeulen",
    "full": "Noor Vermeulen",
    "username": "noor.fictional",
    "tiktok_user": "noorverm_fictional",
    "email": "noor.vermeulen@example.org",
    "phone": "+31 6 00 00 01 23",  # fictional
    "birth": "1996-04-12",
    "city": "Utrecht, Netherlands",
    "bio": "Fictional test persona for the DDP Tracker. Coffee, cycling, plants.",
}
FRIENDS = [
    "Sanne de Wit",
    "Daan Jansen",
    "Lotte Bakker",
    "Milan Visser",
    "Emma Smit",
    "Lucas Mulder",
    "Julia de Boer",
    "Sem Peters",
    "Tess Hendriks",
    "Finn Dekker",
    "Yara El Amrani",
    "Bram Kok",
    "Iris van Leeuwen",
    "Thijs Brouwer",
    "Zoë de Graaf",
]
HANDLES = [n.lower().replace(" ", "_").replace("ë", "e") + "_fic" for n in FRIENDS]
SEARCH_TERMS = [
    "vegan stroopwafel recipe",
    "utrecht cycling routes",
    "monstera care",
    "climate protest",
    "tweede kamer debat",
    "cheap flights lisbon",
    "houseplant pests",
    "running shoes review",
    "data donation study",
    "how to repot a calathea",
    "ajax score",
    "dutch election polls",
    "coffee grinder",
    "rent prices utrecht",
    "podcast recommendations",
]
TOPICS = ["Cycling", "Houseplants", "Coffee", "Travel", "Climate", "Politics", "Cooking", "Running"]
ADVERTISERS = [
    "GreenLeaf Plants BV",
    "VeloFast Bikes",
    "Koffiebar Noord",
    "TravelCheap EU",
    "StudyDutch Online",
    "RunWell Store",
    "Fictional Energy Co.",
]
EMOJI_TEXT = [
    "Zo mooi! 😍",
    "Haha echt waar 😂",
    "Gefeliciteerd! 🎉",
    "Café was top ☕",
    "Tot morgen 👋",
]
UA = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
]
CHANNELS = (
    "Fictional Cycling Channel",
    "Plant Care Daily",
    "Utrecht City Walks",
    "Made-up News NL",
    "Coffee Lab",
)


def meta_text(s: str) -> str:
    """Meta exports write non-ASCII as UTF-8 bytes read as Latin-1 (the well-known mojibake)."""
    return s.encode("utf-8").decode("latin-1")


def tiny_jpeg() -> bytes:
    """A valid 1x1 JPEG, so media files are recognised by MIME type."""
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432"
        "ffc0000b080001000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9"
    )


class _Builder:
    """One package's builder. Each has its own random generator with the same seed, so a
    package is the same on every run, whatever was built before it."""

    def __init__(self, request_date: datetime) -> None:
        self.rng = random.Random(SEED)  # noqa: S311 - fictional demo data, nothing secret
        self.request_date = request_date

    def ts_between(self, start: datetime, end: datetime) -> datetime:
        return start + timedelta(seconds=self.rng.randint(0, int((end - start).total_seconds())))

    def recent(self, n: int, days: int = 365) -> list[datetime]:
        start = self.request_date - timedelta(days=days)
        return sorted((self.ts_between(start, self.request_date) for _ in range(n)), reverse=True)

    def fake_ip(self) -> str:
        return self.rng.choice(["192.0.2.", "198.51.100.", "203.0.113."]) + str(
            self.rng.randint(1, 254)
        )

    def fbid(self) -> str:
        return str(self.rng.randint(10**16, 10**17 - 1))

    # ======================================================================= TikTok
    def tiktok(self) -> Files:
        vid = iter(range(7_400_000_000_000_000_001, 7_500_000_000_000_000_000))

        def link() -> str:
            return f"https://www.tiktokv.com/share/video/{next(vid)}/"

        def chat(friend: str) -> list[dict[str, Any]]:
            msgs = []
            for t in self.recent(self.rng.randint(4, 12), 120):
                sender = self.rng.choice([PERSONA["tiktok_user"], friend])
                msgs.append(
                    {
                        "Date": t.strftime(TIKTOK_DATE),
                        "From": sender,
                        "Content": self.rng.choice([*EMOJI_TEXT, link(), "lol", "ok!"]),
                    }
                )
            return msgs

        chat_partners = HANDLES[:3]
        data: dict[str, Any] = {
            "Activity Summary": None,  # placeholder, removed below (keeps key order readable)
            "Ads and data": {
                "Ad Interests": {"AdInterestCategories": " | ".join(self.rng.sample(TOPICS, 4))},
                "Off TikTok Activity": {
                    "OffTikTokActivityDataList": [
                        {
                            "TimeStamp": t.strftime(TIKTOK_DATE),
                            "Source": self.rng.choice(ADVERTISERS),
                            "Event": self.rng.choice(
                                ["Page View", "Add to Cart", "Search", "Complete Registration"]
                            ),
                        }
                        for t in self.recent(60)
                    ]
                },
            },
            "Comment": {
                "Comments": {
                    "App": 1,
                    "CommentsList": [
                        {
                            "date": t.strftime(TIKTOK_DATE),
                            "comment": self.rng.choice(EMOJI_TEXT),
                            "photo": "N/A",
                            "sticker": "N/A",
                            "video": "N/A",
                            "url": "",
                            "original post link": link(),
                        }
                        for t in self.recent(12)
                    ],
                }
            },
            "Direct Message": {
                "Direct Messages": {
                    "ChatHistory": {f"Chat History with {p}:": chat(p) for p in chat_partners}
                },
                "Group Chat": {"GroupChat": {}},
            },
            "Income+ Wallet": {
                "Coin Purchase History": {"CoinPurchaseHistoryList": None},
                "Transaction History": {"TransactionsList": None},
            },
            "Likes and Favorites": {
                "Favorite Effects": {"FavoriteEffectsList": None},
                "Favorite Hashtags": {
                    "FavoriteHashtagList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "Link": f"https://www.tiktok.com/tag/{self.rng.choice(TOPICS).lower()}",
                        }
                        for t in self.recent(3)
                    ]
                },
                "Favorite Sounds": {
                    "FavoriteSoundList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "Link": f"https://www.tiktok.com/music/sound-{next(vid)}",
                        }
                        for t in self.recent(2)
                    ]
                },
                "Favorite Videos": {
                    "App": 1,
                    "FavoriteVideoList": [
                        {"Date": t.strftime(TIKTOK_DATE), "Link": link()} for t in self.recent(25)
                    ],
                },
                "Like List": {
                    "App": 1,
                    "ItemFavoriteList": [
                        {"date": t.strftime(TIKTOK_DATE), "link": link()} for t in self.recent(80)
                    ],
                },
            },
            "Post": {
                "Posts": {
                    "VideoList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "Link": link(),
                            "Likes": str(self.rng.randint(0, 400)),
                            "Title": self.rng.choice(
                                [
                                    "Morning ride",
                                    "New plant baby",
                                    "Coffee art attempt #3",
                                    "Rainy Utrecht",
                                ]
                            ),
                            "Sound": "original sound",
                            "Location": self.rng.choice(["", "Utrecht"]),
                            "CoverImage": f"https://p16-sign-va.tiktokcdn.com/obj/fictional-cover-{next(vid)}.jpeg",
                            "WhoCanView": "Everyone",
                            "AllowComments": "Yes",
                            "AllowStitches": "Yes",
                            "AllowDuets": "Yes",
                            "AllowStickers": "Yes",
                            "AllowSharingToStory": "Yes",
                            "ContentDisclosure": "",
                            "AIGeneratedContent": "No",
                            "AlternateText": "",
                            "AddYoursText": "",
                            "NumberOfCollections": str(self.rng.randint(0, 20)),
                        }
                        for t in self.recent(6)
                    ]
                }
            },
            "Profile And Settings": {
                "Profile Info": {
                    "App": 1,
                    "ProfileMap": {
                        "userName": PERSONA["tiktok_user"],
                        "displayName": PERSONA["first"],
                        "emailAddress": PERSONA["email"],
                        "telephoneNumber": PERSONA["phone"],
                        "birthDate": "12-Apr-1996",
                        "bioDescription": PERSONA["bio"],
                        "accountRegion": "NL",
                        "inferredGender": "Female",
                        "followerCount": 42,
                        "followingCount": 57,
                        "profilePhoto": "https://p16-sign-va.tiktokcdn.com/obj/fictional-avatar.jpeg",
                        "profileVideo": "",
                        "instagramLink": "",
                        "youtubeLink": "",
                        "lemon8Link": "",
                        "fundraiser": "",
                        "PlatformInfo": [],
                    },
                },
                "Follower": {
                    "App": 1,
                    "IsFastLane": False,
                    "FansList": [
                        {"Date": t.strftime(TIKTOK_DATE), "UserName": h}
                        for t, h in zip(self.recent(8), HANDLES[3:11], strict=False)
                    ],
                },
                "Following": {
                    "App": 1,
                    "IsFastLane": False,
                    "Following": [
                        {"Date": t.strftime(TIKTOK_DATE), "UserName": h}
                        for t, h in zip(self.recent(10), HANDLES[:10], strict=False)
                    ],
                },
                "Block List": {"App": 1, "BlockList": None},
                "Settings": {
                    "App": 1,
                    "SettingsMap": {
                        "Allow DownLoad": "On",
                        "Allow Others to Find Me": "On",
                        "Private Account": "Off",
                        "Personalized Ads": "On",
                        "App Language": "en",
                        "Web Language": "en",
                        "Who Can Send Me Message": "Friends",
                        "Who Can Post Comments": "Everyone",
                        "Who Can Duet With Me": "Everyone",
                        "Who Can Stitch with your videos": "Everyone",
                        "Who Can View Videos I Liked": "Only Me",
                        "Filter Comments": "Off",
                        "Interests": " | ".join(self.rng.sample(TOPICS, 3)),
                        "Push Notification": {
                            "Desktop notification": "Off",
                            "New Fans": "On",
                            "New Comments on My Video": "On",
                            "New Likes on My Video": "Off",
                        },
                        "Content Preferences": {
                            "Keyword filters for videos in For You feed": [],
                            "Keyword filters for videos in Following feed": [],
                            "Video Languages Preferences": ["English", "Dutch"],
                        },
                    },
                },
            },
            "Tiktok Live": {
                "Go Live History": {"GoLiveList": None},
                "Watch Live History": {
                    "WatchLiveMap": {
                        str(self.rng.randint(10**18, 10**19 - 1)): {
                            "WatchTime": t.strftime(TIKTOK_DATE),
                            "Link": f"https://www.tiktok.com/live/{next(vid)}",
                            "Comments": [],
                            "Questions": None,
                        }
                        for t in self.recent(3)
                    }
                },
            },
            "TikTok Shop": {
                "Order History": {"OrderHistories": None},
                "Product Browsing History": {"ProductBrowsingHistories": None},
            },
            "Your Activity": {
                "Activity Summary": {
                    "ActivitySummaryMap": {
                        "videosCommentedOnSinceAccountRegistration": 12,
                        "videosSharedSinceAccountRegistration": 9,
                        "videosWatchedToTheEndSinceAccountRegistration": 1450,
                        "note": "This summary is an approximation.",
                    }
                },
                "Hashtag": {
                    "HashtagList": [
                        {
                            "HashtagName": t.lower(),
                            "HashtagLink": f"https://www.tiktok.com/tag/{t.lower()}",
                        }
                        for t in self.rng.sample(TOPICS, 4)
                    ]
                },
                "Login History": {
                    "LoginHistoryList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "IP": self.fake_ip(),
                            "DeviceModel": self.rng.choice(["iPhone15,3", "Pixel 8"]),
                            "DeviceSystem": self.rng.choice(["iOS 18.5", "Android 15"]),
                            "NetworkType": self.rng.choice(["Wi-Fi", "4G"]),
                            "Carrier": self.rng.choice(["Fictional Mobile NL", ""]),
                        }
                        for t in self.recent(30)
                    ]
                },
                "Most Recent Location Data": {
                    "LocationData": {
                        "Date": self.request_date.strftime(TIKTOK_DATE),
                        "GpsData": "",
                        "LastRegion": "NL",
                    }
                },
                "Searches": {
                    "SearchList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "SearchTerm": self.rng.choice(SEARCH_TERMS),
                        }
                        for t in self.recent(40)
                    ]
                },
                "Share History": {
                    "ShareHistoryList": [
                        {
                            "Date": t.strftime(TIKTOK_DATE),
                            "SharedContent": "video",
                            "Link": link(),
                            "Method": self.rng.choice(["whatsapp", "copy link", "instagram_dm"]),
                        }
                        for t in self.recent(5)
                    ]
                },
                "Watch History": {
                    "VideoList": [
                        {"Date": t.strftime(TIKTOK_DATE), "Link": link()}
                        for t in self.recent(300, 90)
                    ]
                },
            },
        }
        del data["Activity Summary"]
        return {TIKTOK_FILE: data}

    # ==================================================================== Instagram
    def instagram(self) -> Files:
        me = PERSONA["username"]
        root = ""  # Instagram zips have no wrapper folder

        def sld(value: str, href: str, t: datetime) -> list[dict[str, Any]]:
            return [{"href": href, "value": value, "timestamp": int(t.timestamp())}]

        def label_item(t: datetime, url: str, owner: str) -> dict[str, Any]:
            return {
                "timestamp": int(t.timestamp()),
                "media": [],
                "label_values": [
                    {"label": "URL", "value": url, "href": url},
                    {
                        "dict": [
                            {
                                "dict": [
                                    {"label": "URL", "value": f"https://www.instagram.com/{owner}"},
                                    {
                                        "label": "Name",
                                        "value": owner.replace("_fic", "")
                                        .replace("_", " ")
                                        .title(),
                                    },
                                    {"label": "Username", "value": owner},
                                ],
                                "title": "",
                            }
                        ],
                        "title": "Owner",
                    },
                ],
                "fbid": self.fbid(),
            }

        def post_url() -> str:
            return (
                "https://www.instagram.com/p/"
                + "".join(
                    self.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz0123456789_-")
                    for _ in range(11)
                )
                + "/"
            )

        f: Files = {}
        # connections
        f["connections/followers_and_following/followers_1.json"] = [
            {
                "title": "",
                "media_list_data": [],
                "string_list_data": sld(h, f"https://www.instagram.com/{h}", t),
            }
            for t, h in zip(self.recent(12), HANDLES[:12], strict=False)
        ]
        f["connections/followers_and_following/following.json"] = {
            "relationships_following": [
                {
                    "title": h,
                    "string_list_data": [
                        {
                            "href": f"https://www.instagram.com/_u/{h}",
                            "timestamp": int(t.timestamp()),
                        }
                    ],
                }
                for t, h in zip(self.recent(14), HANDLES[1:15], strict=False)
            ]
        }
        f["connections/followers_and_following/pending_follow_requests.json"] = {
            "relationships_follow_requests_sent": [
                {
                    "title": "",
                    "media_list_data": [],
                    "string_list_data": sld(
                        "fictional_bakery_fic",
                        "https://www.instagram.com/fictional_bakery_fic",
                        self.request_date - timedelta(days=3),
                    ),
                }
            ]
        }
        # activity
        f["your_instagram_activity/likes/liked_posts.json"] = [
            label_item(t, post_url(), self.rng.choice(HANDLES)) for t in self.recent(45)
        ]
        f["your_instagram_activity/saved/saved_posts.json"] = [
            label_item(t, post_url(), self.rng.choice(HANDLES)) for t in self.recent(15)
        ]
        f["your_instagram_activity/comments/post_comments_1.json"] = [
            {
                "media_list_data": [{"uri": ""}],
                "string_map_data": {
                    "Comment": {"value": meta_text(self.rng.choice(EMOJI_TEXT))},
                    "Media Owner": {"value": self.rng.choice(HANDLES)},
                    "Time": {"timestamp": int(t.timestamp())},
                },
            }
            for t in self.recent(9)
        ]
        f["your_instagram_activity/media/stories.json"] = {
            "ig_stories": [
                {
                    "uri": f"media/stories/{t:%Y%m}/{self.rng.randint(10**17, 10**18)}.jpg",
                    "creation_timestamp": int(t.timestamp()),
                    "title": "",
                    "media_variants": [],
                    "dubbing_info": [],
                    "cross_post_source": {"source_app": "FB"},
                    "media_metadata": {
                        "photo_metadata": {
                            "exif_data": [
                                {
                                    "device_id": str(uuid.UUID(int=self.rng.getrandbits(128))),
                                    "camera_position": "back",
                                    "source_type": "camera",
                                    "date_time_original": t.strftime("%Y:%m:%d %H:%M:%S"),
                                }
                            ]
                        }
                    },
                }
                for t in self.recent(4, 60)
            ]
        }
        for story in f["your_instagram_activity/media/stories.json"]["ig_stories"]:
            f[story["uri"]] = tiny_jpeg()
        f["your_instagram_activity/media/profile_photos.json"] = {
            "ig_profile_picture": [
                {
                    "uri": "media/other/0.jpg",
                    "creation_timestamp": int(
                        (self.request_date - timedelta(days=400)).timestamp()
                    ),
                    "title": "",
                    "is_active_profile": True,
                }
            ]
        }
        f["media/other/0.jpg"] = tiny_jpeg()
        f["your_instagram_activity/story_interactions/story_likes.json"] = {
            "story_activities_story_likes": [
                {"title": h, "string_list_data": [{"timestamp": int(t.timestamp())}]}
                for t, h in zip(self.recent(10), self.rng.choices(HANDLES, k=10), strict=False)
            ]
        }
        f["your_instagram_activity/story_interactions/polls.json"] = {
            "story_activities_polls": [
                {
                    "title": h,
                    "string_list_data": [
                        {
                            "value": self.rng.choice(["Yes", "No", "🌱", "☕"]),
                            "timestamp": int(t.timestamp()),
                        }
                    ],
                }
                for t, h in zip(self.recent(6), self.rng.choices(HANDLES, k=6), strict=False)
            ]
        }
        # messages: a few threads, folder names are "<handle>_<id>"
        for h in HANDLES[:4]:
            thread = f"{h.replace('_', '')}_{self.rng.randint(10**15, 10**16 - 1)}"
            msgs: list[dict[str, Any]] = []
            for t in self.recent(self.rng.randint(5, 20), 150):
                sender = self.rng.choice(
                    [PERSONA["full"], h.replace("_fic", "").replace("_", " ").title()]
                )
                m: dict[str, Any] = {
                    "sender_name": meta_text(sender),
                    "timestamp_ms": int(t.timestamp() * 1000),
                    "content": meta_text(
                        self.rng.choice([*EMOJI_TEXT, "Zie je morgen?", "Ha! 🤣", "Klopt"])
                    ),
                    "is_geoblocked_for_viewer": False,
                    "is_unsent_image_by_messenger_kid_parent": False,
                }
                if self.rng.random() < REACTION_CHANCE:
                    m["reactions"] = [
                        {"reaction": meta_text("❤"), "actor": meta_text(PERSONA["full"])}
                    ]
                if self.rng.random() < SHARE_CHANCE:
                    m["share"] = {
                        "link": post_url(),
                        "share_text": "",
                        "original_content_owner": self.rng.choice(HANDLES),
                    }
                msgs.append(m)
            f[f"your_instagram_activity/messages/inbox/{thread}/message_1.json"] = {
                "participants": [
                    {"name": meta_text(PERSONA["full"])},
                    {"name": h.replace("_fic", "").replace("_", " ").title()},
                ],
                "messages": msgs,
                "title": h.replace("_fic", "").replace("_", " ").title(),
                "is_still_participant": True,
                "thread_path": f"inbox/{thread}",
                "magic_words": [],
            }
        f["your_instagram_activity/other_activity/your_information_download_requests.json"] = {
            "account_history_data_request_history": [
                {
                    "title": "",
                    "media_map_data": {},
                    "string_map_data": {
                        "Time": {
                            "href": "",
                            "value": "",
                            "timestamp": int(self.request_date.timestamp()),
                        },
                        "Format": {"href": "", "value": "JSON", "timestamp": 0},
                    },
                }
            ]
        }
        # ads
        f["ads_information/ads_and_topics/ads_viewed.json"] = [
            {
                **label_item(t, post_url(), self.rng.choice(HANDLES)),
                "label_values": [
                    {"label": "Author", "value": self.rng.choice(ADVERTISERS)},
                    {"label": "URL", "vec": [{"value": post_url(), "href": post_url()}]},
                ],
            }
            for t in self.recent(60, 30)
        ]
        f["ads_information/ads_and_topics/videos_watched.json"] = [
            {
                "timestamp": int(t.timestamp()),
                "media": [],
                "fbid": self.fbid(),
                "label_values": [{"label": "Author", "value": self.rng.choice(HANDLES)}],
            }
            for t in self.recent(80, 30)
        ]
        f[
            "ads_information/instagram_ads_and_businesses/advertisers_using_your_activity_or_information.json"
        ] = {
            "ig_custom_audiences_all_types": [
                {
                    "advertiser_name": a,
                    "has_data_file_custom_audience": self.rng.random() < EVEN_CHANCE,
                    "has_remarketing_custom_audience": self.rng.random() < EVEN_CHANCE,
                    "has_in_person_store_visit": False,
                }
                for a in ADVERTISERS
            ]
        }
        # logged information
        f["logged_information/recent_searches/word_or_phrase_searches.json"] = {
            "searches_keyword": [
                {
                    "title": "",
                    "media_map_data": {},
                    "string_map_data": {
                        "Search": {
                            "href": "",
                            "value": self.rng.choice(SEARCH_TERMS),
                            "timestamp": 0,
                        },
                        "Time": {"href": "", "value": "", "timestamp": int(t.timestamp())},
                    },
                }
                for t in self.recent(18)
            ]
        }
        f["logged_information/recent_searches/profile_searches.json"] = {
            "searches_user": [
                {
                    "title": "",
                    "media_map_data": {},
                    "string_map_data": {
                        "Search": {"href": "", "value": h, "timestamp": 0},
                        "Time": {"href": "", "value": "", "timestamp": int(t.timestamp())},
                    },
                }
                for t, h in zip(self.recent(8), HANDLES, strict=False)
            ]
        }
        f["logged_information/link_history/link_history.json"] = [
            {
                "timestamp": int(t.timestamp()),
                "media": [],
                "fbid": self.fbid(),
                "label_values": [
                    {
                        "label": "Website name",
                        "value": self.rng.choice(["Example News", "Fictional Blog", "Plant Shop"]),
                    },
                    {
                        "label": "Website URL",
                        "value": f"https://www.example.com/article/{self.rng.randint(1000, 9999)}",
                    },
                ],
            }
            for t in self.recent(20)
        ]
        # personal information
        f["personal_information/personal_information/personal_information.json"] = {
            "profile_user": [
                {
                    "media_map_data": {
                        "Profile Photo": {
                            "uri": "media/other/0.jpg",
                            "creation_timestamp": int(
                                (self.request_date - timedelta(days=400)).timestamp()
                            ),
                            "title": "",
                            "cross_post_source": {"source_app": "FB"},
                            "media_metadata": {"camera_metadata": {"has_camera_metadata": False}},
                        }
                    },
                    "string_map_data": {
                        "Email": {"href": "", "value": PERSONA["email"], "timestamp": 0},
                        "Phone Confirmed": {"href": "", "value": "True", "timestamp": 0},
                        "Username": {"href": "", "value": me, "timestamp": 0},
                        "Name": {"href": "", "value": PERSONA["full"], "timestamp": 0},
                        "Bio": {"href": "", "value": PERSONA["bio"], "timestamp": 0},
                        "Gender": {"href": "", "value": "female", "timestamp": 0},
                        "Date of birth": {"href": "", "value": PERSONA["birth"], "timestamp": 0},
                        "Private Account": {"href": "", "value": "False", "timestamp": 0},
                    },
                    "title": "",
                }
            ]
        }
        f["personal_information/information_about_you/locations_of_interest.json"] = {
            "label_values": [
                {
                    "label": "Locations of interest",
                    "vec": [{"value": "Utrecht"}, {"value": "Amsterdam"}, {"value": "Lisbon"}],
                }
            ]
        }
        # security
        f["security_and_login_information/login_and_profile_creation/login_activity.json"] = {
            "account_history_login_history": [
                {
                    "title": t.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "media_map_data": {},
                    "string_map_data": {
                        "Cookie Name": {
                            "href": "",
                            "value": uuid.UUID(int=self.rng.getrandbits(128)).hex[:24],
                            "timestamp": 0,
                        },
                        "IP Address": {"href": "", "value": self.fake_ip(), "timestamp": 0},
                        "Language Code": {"href": "", "value": "en", "timestamp": 0},
                        "Time": {"href": "", "value": "", "timestamp": int(t.timestamp())},
                        "User Agent": {"href": "", "value": self.rng.choice(UA), "timestamp": 0},
                    },
                }
                for t in self.recent(14)
            ]
        }
        f["security_and_login_information/login_and_profile_creation/signup_details.json"] = {
            "account_history_registration_info": [
                {
                    "title": "",
                    "media_map_data": {},
                    "string_map_data": {
                        "Username": {"href": "", "value": me, "timestamp": 0},
                        "Email": {"href": "", "value": PERSONA["email"], "timestamp": 0},
                        "Time": {
                            "href": "",
                            "value": "",
                            "timestamp": int(datetime(2014, 6, 3, tzinfo=UTC).timestamp()),
                        },
                        "Device": {"href": "", "value": "iPhone", "timestamp": 0},
                    },
                }
            ]
        }
        f["preferences/settings/consents.json"] = {"consent_history": []}
        return {root + k: v for k, v in f.items()}

    # ===================================================================== Facebook
    def facebook(self) -> Files:
        me = PERSONA["full"]
        f: Files = {}

        def ts(t: datetime) -> int:
            return int(t.timestamp())

        f["connections/friends/your_friends.json"] = {
            "friends_v2": [
                {"name": meta_text(n), "timestamp": ts(t)}
                for t, n in zip(self.recent(15, 3000), FRIENDS, strict=False)
            ]
        }
        f["connections/friends/sent_friend_requests.json"] = {
            "sent_requests_v2": [
                {
                    "name": "Fictional Neighbour",
                    "timestamp": ts(self.request_date - timedelta(days=20)),
                }
            ]
        }
        f["connections/friends/removed_friends.json"] = {
            "deleted_friends_v2": [
                {"name": "Old Classmate", "timestamp": ts(self.request_date - timedelta(days=700))}
            ]
        }
        f["connections/followers/who_you've_followed.json"] = {
            "following_v3": [
                {"name": p, "timestamp": ts(t)}
                for t, p in zip(
                    self.recent(6, 2000),
                    [
                        "Utrecht Centraal Fietsers",
                        "Plant Swap NL",
                        "Fictional News NL",
                        "Koffiebar Noord",
                        "Climate Action Utrecht",
                        "Running Club Oost",
                    ],
                    strict=False,
                )
            ]
        }
        f["your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json"] = [
            {
                "timestamp": ts(t),
                "data": [
                    {
                        "post": meta_text(
                            self.rng.choice(
                                [
                                    "Eerste ritje van het seizoen 🚲",
                                    "New plant, who dis? 🌿",
                                    "Café hopping in Utrecht ☕",
                                    "Happy birthday Sanne! 🎉",
                                ]
                            )
                        )
                    }
                ],
                "attachments": (
                    [
                        {
                            "data": [
                                {
                                    "media": {
                                        "uri": f"your_facebook_activity/posts/media/{t:%Y%m}/{self.rng.randint(10**14, 10**15)}.jpg",
                                        "creation_timestamp": ts(t),
                                        "title": "",
                                        "description": "",
                                    }
                                }
                            ]
                        }
                    ]
                    if self.rng.random() < EVEN_CHANCE
                    else []
                ),
                "title": meta_text(f"{me} updated her status."),
            }
            for t in self.recent(20, 1500)
        ]
        for post in f[
            "your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json"
        ]:
            for att in post["attachments"]:
                f[att["data"][0]["media"]["uri"]] = tiny_jpeg()
        f["your_facebook_activity/comments_and_reactions/comments.json"] = {
            "comments_v2": [
                {
                    "timestamp": ts(t),
                    "data": [
                        {
                            "comment": {
                                "timestamp": ts(t),
                                "comment": meta_text(self.rng.choice(EMOJI_TEXT)),
                                "author": meta_text(me),
                            }
                        }
                    ],
                    "title": meta_text(f"{me} commented on {self.rng.choice(FRIENDS)}'s post."),
                }
                for t in self.recent(25, 1500)
            ]
        }
        f["your_facebook_activity/comments_and_reactions/likes_and_reactions_1.json"] = [
            {
                "timestamp": ts(t),
                "data": [
                    {
                        "reaction": {
                            "reaction": self.rng.choice(["LIKE", "LOVE", "HAHA", "WOW", "CARE"]),
                            "actor": meta_text(me),
                        }
                    }
                ],
                "title": meta_text(f"{me} reacted to {self.rng.choice(FRIENDS)}'s post."),
            }
            for t in self.recent(90, 1500)
        ]
        f["your_facebook_activity/groups/your_group_membership_activity.json"] = {
            "groups_joined_v2": [
                {
                    "timestamp": ts(t),
                    "data": [{"name": g}],
                    "title": f"{me} became a member of {g}.",
                }
                for t, g in zip(
                    self.recent(4, 2000),
                    [
                        "Plant Swap NL",
                        "Utrecht Housing Exchange",
                        "Fietsen Utrecht",
                        "Board Games Oost",
                    ],
                    strict=False,
                )
            ]
        }
        f["your_facebook_activity/events/your_event_responses.json"] = {
            "event_responses_v2": {
                "events_joined": [
                    {
                        "name": e,
                        "start_timestamp": ts(t),
                        "end_timestamp": ts(t + timedelta(hours=3)),
                    }
                    for t, e in zip(
                        self.recent(3, 400),
                        ["Plant swap autumn", "Climate march", "Board game night"],
                        strict=False,
                    )
                ],
                "events_declined": [],
                "events_interested": [],
            }
        }
        f["your_facebook_activity/pages/pages_you've_liked.json"] = {
            "page_likes_v2": [
                {"name": p, "timestamp": ts(t)}
                for t, p in zip(
                    self.recent(5, 3000),
                    [
                        "Koffiebar Noord",
                        "VeloFast Bikes",
                        "Fictional News NL",
                        "Plant Swap NL",
                        "Utrecht Library",
                    ],
                    strict=False,
                )
            ]
        }
        for friend in FRIENDS[:3]:
            slug = friend.lower().replace(" ", "") + "_" + str(self.rng.randint(10**15, 10**16 - 1))
            msgs = [
                {
                    "sender_name": meta_text(self.rng.choice([me, friend])),
                    "timestamp_ms": int(t.timestamp() * 1000),
                    "content": meta_text(
                        self.rng.choice([*EMOJI_TEXT, "Heb je tijd zaterdag?", "Ja leuk!"])
                    ),
                    "is_geoblocked_for_viewer": False,
                    "is_unsent_image_by_messenger_kid_parent": False,
                }
                for t in self.recent(self.rng.randint(6, 20), 400)
            ]
            f[f"your_facebook_activity/messages/inbox/{slug}/message_1.json"] = {
                "participants": [{"name": meta_text(friend)}, {"name": meta_text(me)}],
                "messages": msgs,
                "title": meta_text(friend),
                "is_still_participant": True,
                "thread_path": f"inbox/{slug}",
                "magic_words": [],
            }
        f["your_facebook_activity/other_activity/pokes.json"] = {
            "pokes_v2": {
                "data": [
                    {
                        "poker": "Daan Jansen",
                        "pokee": me,
                        "rep": 3,
                        "timestamp": ts(self.request_date - timedelta(days=50)),
                    }
                ]
            }
        }
        f["your_facebook_activity/facebook_marketplace/items_sold.json"] = {
            "items_selling_v2": [
                {
                    "title": "Vintage bike basket",
                    "price": "EUR15.00",
                    "seller": me,
                    "created_timestamp": ts(self.request_date - timedelta(days=120)),
                    "category": "Bicycles",
                    "marketplace": "Marketplace",
                    "location": {"name": "Utrecht"},
                    "description": "",
                }
            ]
        }
        f["logged_information/search/your_search_history.json"] = {
            "searches_v2": [
                {
                    "timestamp": ts(t),
                    "attachments": [{"data": [{"text": meta_text(s)}]}],
                    "data": [{"text": meta_text(s)}],
                    "title": "You searched Facebook",
                }
                for t, s in zip(self.recent(15), self.rng.choices(SEARCH_TERMS, k=15), strict=False)
            ]
        }
        f["logged_information/location/primary_location.json"] = {
            "primary_location_v2": {
                "city_region_pairs": [["Utrecht", "Utrecht"]],
                "zipcode": ["3511"],
            }
        }
        f["logged_information/location/timezone.json"] = {"timezone_v2": "Europe/Amsterdam"}
        f["logged_information/interactions/recently_viewed.json"] = {
            "recently_viewed": [
                {
                    "name": "Videos",
                    "description": "Videos you've watched",
                    "entries": [
                        {
                            "timestamp": ts(t),
                            "data": {
                                "name": f"Fictional video {i}",
                                "uri": f"https://www.facebook.com/watch/?v={self.fbid()}",
                            },
                        }
                        for i, t in enumerate(self.recent(12, 60))
                    ],
                }
            ]
        }
        f["logged_information/other_logged_information/ads_interests.json"] = {
            "topics_v2": self.rng.sample(TOPICS, 6)
        }
        f["ads_information/advertisers_you've_interacted_with.json"] = [
            {
                "timestamp": ts(t),
                "media": [],
                "fbid": self.fbid(),
                "label_values": [
                    {"label": "Title", "value": self.rng.choice(ADVERTISERS)},
                    {"label": "Action", "value": "Clicked ad"},
                ],
            }
            for t in self.recent(8)
        ]
        f["ads_information/other_categories_used_to_reach_you.json"] = {
            "bcts": ["Frequent traveller", "Owns an iPhone", "Early technology adopter"]
        }
        f["apps_and_websites_off_of_facebook/your_activity_off_meta_technologies.json"] = [
            {
                "timestamp": ts(t),
                "media": [],
                "fbid": self.fbid(),
                "label_values": [
                    {"label": "App", "value": self.rng.choice(ADVERTISERS)},
                    {
                        "label": "Event",
                        "value": self.rng.choice(
                            ["PAGE_VIEW", "ADD_TO_CART", "SEARCH", "PURCHASE"]
                        ),
                    },
                    {"label": "ID", "value": self.fbid()},
                ],
            }
            for t in self.recent(50, 180)
        ]
        f["personal_information/profile_information/profile_information.json"] = {
            "profile_v2": {
                "name": {
                    "full_name": me,
                    "first_name": PERSONA["first"],
                    "middle_name": "",
                    "last_name": PERSONA["last"],
                },
                "emails": {
                    "emails": [PERSONA["email"]],
                    "previous_emails": [],
                    "pending_emails": [],
                    "ad_account_emails": [],
                },
                "birthday": {"year": 1996, "month": 4, "day": 12},
                "gender": {"gender_option": "FEMALE", "pronoun": "FEMALE"},
                "current_city": {
                    "name": PERSONA["city"],
                    "timestamp": ts(self.request_date - timedelta(days=900)),
                },
                "hometown": {
                    "name": "Zwolle, Netherlands",
                    "timestamp": ts(self.request_date - timedelta(days=3000)),
                },
                "relationship": {
                    "status": "In a relationship",
                    "timestamp": ts(self.request_date - timedelta(days=500)),
                },
                "family_members": [
                    {
                        "name": "Fictional Sibling",
                        "relation": "Sister",
                        "timestamp": ts(self.request_date - timedelta(days=2000)),
                    }
                ],
                "education_experiences": [
                    {
                        "name": "Fictional University of Utrecht",
                        "graduated": True,
                        "concentrations": ["Sociology"],
                        "school_type": "College",
                        "timestamp": ts(self.request_date - timedelta(days=2500)),
                    }
                ],
                "work_experiences": [
                    {
                        "employer": "Fictional Research Institute",
                        "title": "Research assistant",
                        "start_timestamp": ts(self.request_date - timedelta(days=1200)),
                        "timestamp": ts(self.request_date - timedelta(days=1200)),
                    }
                ],
                "languages": [
                    {"name": "Dutch", "timestamp": 0},
                    {"name": "English", "timestamp": 0},
                ],
                "phone_numbers": [
                    {"phone_type": "Mobile", "phone_number": PERSONA["phone"], "verified": True}
                ],
                "registration_timestamp": ts(datetime(2011, 9, 1, tzinfo=UTC)),
                "profile_uri": "https://www.facebook.com/noor.fictional",
            }
        }
        f["security_and_login_information/logins_and_logouts.json"] = {
            "account_accesses_v2": [
                {
                    "action": self.rng.choice(["Login", "Log out", "Session updated"]),
                    "timestamp": ts(t),
                    "site": self.rng.choice(["www.facebook.com", "Facebook app"]),
                    "ip_address": self.fake_ip(),
                }
                for t in self.recent(30)
            ]
        }
        f["security_and_login_information/where_you're_logged_in.json"] = {
            "active_sessions_v2": [
                {
                    "created_timestamp": ts(t),
                    "updated_timestamp": ts(t + timedelta(days=5)),
                    "ip_address": self.fake_ip(),
                    "user_agent": self.rng.choice(UA),
                    "datr_cookie": uuid.UUID(int=self.rng.getrandbits(128)).hex[:24],
                    "device": "",
                    "location": "Utrecht, Netherlands",
                    "app": self.rng.choice(["Facebook for iPhone", "Chrome"]),
                    "session_type": "",
                }
                for t in self.recent(3, 60)
            ]
        }
        f["preferences/preferences/language_and_locale.json"] = {
            "language_and_locale_v2": [
                {
                    "name": "Language settings",
                    "description": "Your preferred language",
                    "children": [
                        {"name": "Selected language", "entries": [{"data": {"value": "en_GB"}}]}
                    ],
                }
            ]
        }
        return {f"facebook-noorfictional-2026-09-15-AbCdEf12/{k}": v for k, v in f.items()}

    # ====================================================================== YouTube
    def youtube(self) -> Files:
        """A small Google Takeout: watch and search history as JSON (the timestamps carry a
        Z), subscriptions as CSV."""
        stamp = "%Y-%m-%dT%H:%M:%S.000Z"
        root = "Takeout/YouTube and YouTube Music/"
        watched = [
            {
                "header": "YouTube",
                "title": f"Watched Fictional video {number}",
                "titleUrl": f"https://www.youtube.com/watch?v=fictional{number:03d}",
                "subtitles": [
                    {
                        "name": channel,
                        "url": f"https://www.youtube.com/channel/UCfictional{CHANNELS.index(channel):04d}",
                    }
                ],
                "time": moment.strftime(stamp),
                "products": ["YouTube"],
                "activityControls": ["YouTube watch history"],
            }
            for number, (moment, channel) in enumerate(
                zip(self.recent(40, 90), self.rng.choices(CHANNELS, k=40), strict=True)
            )
        ]
        searched = [
            {
                "header": "YouTube",
                "title": f"Searched for {term}",
                "titleUrl": "https://www.youtube.com/results?search_query="
                + term.replace(" ", "+"),
                "time": moment.strftime(stamp),
                "products": ["YouTube"],
                "activityControls": ["YouTube search history"],
            }
            for moment, term in zip(
                self.recent(12), self.rng.choices(SEARCH_TERMS, k=12), strict=True
            )
        ]
        subscriptions = "Channel Id,Channel Url,Channel Title\n" + "".join(
            f"UCfictional{number:04d},http://www.youtube.com/channel/UCfictional{number:04d},{channel}\n"
            for number, channel in enumerate(CHANNELS)
        )
        return {
            f"{root}history/watch-history.json": watched,
            f"{root}history/search-history.json": searched,
            f"{root}subscriptions/subscriptions.csv": subscriptions,
        }


def tiktok(request_date: datetime = SEPTEMBER) -> Files:
    return _Builder(request_date).tiktok()


def tiktok_march() -> Files:
    """The TikTok package as it looked six months earlier, so that the September one has
    something to differ from: the section Your Activity is still called Activity and its
    watch history Video Browsing History, there is no live section, the like list's dates
    are ISO 8601 with a Z, and the profile has a field that was dropped since."""
    data = tiktok(MARCH)[TIKTOK_FILE]
    activity = data.pop("Your Activity")
    activity["Video Browsing History"] = activity.pop("Watch History")
    data["Activity"] = activity
    del data["Tiktok Live"]
    for like in data["Likes and Favorites"]["Like List"]["ItemFavoriteList"]:
        liked_at = datetime.strptime(like["date"], TIKTOK_DATE).replace(tzinfo=UTC)
        like["date"] = liked_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["Profile And Settings"]["Profile Info"]["ProfileMap"]["likesReceived"] = "57"
    return {TIKTOK_FILE: data}


def instagram() -> Files:
    return _Builder(SEPTEMBER).instagram()


def facebook() -> Files:
    return _Builder(SEPTEMBER).facebook()


def youtube() -> Files:
    return _Builder(SEPTEMBER).youtube()


def build_zip(files: Files) -> bytes:
    """The package as a zip. Members get a fixed timestamp, so the same files always give the
    same bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            if not isinstance(content, (bytes, str)):
                content = json.dumps(content, indent=2, ensure_ascii=True)  # noqa: PLW2901 - the member's content, as text
            archive.writestr(info, content)
    return buffer.getvalue()
