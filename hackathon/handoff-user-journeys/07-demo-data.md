# 07. Demo data

## Why

A fresh install has no platforms, uploads, annotations or representations. Only the representation vocabulary is created by a migration. The live site's data cannot be exported: there is no API, and nobody has a database dump. So the prototype needs its own fictional data.

## The sample DDPs (already made and tested)

Location: `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\sample-ddps\`. A copy of the generator is also in the Project as `claude/make_sample_ddps.py`.

| File | Platform | Content |
|---|---|---|
| `facebook-noorfictional-2026-09-15-AbCdEf12.zip` | Facebook | 40 files, 290 parsed nodes; has a wrapper folder named like the zip (the parser removes it) |
| `instagram-noor.fictional-2026-09-15-XyZ12345.zip` | Instagram | 31 files, 298 parsed nodes |
| `tiktok_fictional_2026-09-15.zip` | TikTok | `user_data_tiktok.json`, 207 parsed nodes |

**The persona and data:**

- The persona is "Noor Vermeulen" (`noor.fictional`), from Utrecht, with 15 fictional friends.
- The data is fictional throughout:
  - e-mail addresses use `example.org`;
  - IP addresses come from the documentation ranges;
  - phone numbers are fictional.
- Structures are modelled on the live tracker's 2026 trees.

`make_sample_ddps.py` regenerates them deterministically (fixed seed), with Python 3.10 or later and no extra packages.

**Upload parameters used in testing:**

| Field | Value |
|---|---|
| Request date | 2026-09-15 |
| Request mode | `DL_BROWSER` |
| Request format | `json` |
| Language | `en` |
| File format | `zip` |

**Tested flow:** all three were uploaded through the real upload form, parsed, approved as "first of its kind" by staff, and registered. The explorer and review pages loaded. The script is `load_sample_ddps_example.py` in this folder.

## `seed_demo` specification

**Command:** `uv run manage.py seed_demo` (in the `journeys` app).

**Behaviour:**

- **Idempotent:** running it twice changes nothing the second time. Look up by slug, name or path before creating.
- **A `--reset` flag (optional):** removes only what `seed_demo` created. Mark created rows, for example with a known demo user as `uploaded_by` / `updated_by`.
- **Refuses to run when `DEBUG` is false**, unless `--force` is given, so it never runs in production by accident.
- **Prints a short summary at the end,** including the demo admin's login.

**What it creates:**

1. **A demo admin**, `demo-admin@example.org`: staff and superuser, with a verified `EmailAddress` and a local-only password (print it).
2. **Platforms:** Facebook (`facebook`), Instagram (`instagram`), TikTok (`tiktok`). Optionally also YouTube (`youtube`) with no uploads, to show an empty state.
3. **Uploads:**
   - **Source of the files:** do not commit binary zips to the repository. Instead, move the generator into the app (for example `ddp_tracker/journeys/demo_ddps.py`) so it builds the zips in memory.
   - **The three September packages.**
   - **One extra, earlier TikTok package**, requested 2026-03-15, so change detection has something to show. Differences from the September one:
     - older section names, such as `Activity › Video Browsing History` instead of `Your Activity › Watch History` (both exist on the live tracker);
     - no `Tiktok Live` section;
     - one field with a different date format.

     Upload it **before** the September one. The September upload then shows New, Changed and moved or renamed suggestions in its review.
   - **Go through the real code path:** create the `Upload` with the file, run the parse task, and then:
     - handle plausibility with `ddps.checks` (`approve` for "first of its kind"; `confirm` then `approve` if an upload is marked dissimilar);
     - make sure it ends up registered (`schemas.services.register_upload` is called by the normal flow).

     Check `ddps/tasks.py` and `ddps/checks.py` for the current function names.
4. **Annotations:** about 6 to 10 per platform, linked to real locations by path. Suggestions below; check the exact paths in the seeded explorer, because variable keys become `{*}`.
5. **Representations:** 2 to 4 per platform, on list items whose main type is object. Use the seeded vocabulary (below).
6. **Example values:** a few per annotated data point, all fictional, `source: "user_input"`.
7. **Optionally, one open suggestion** from a second, non-staff demo user, so the suggestion queue is not empty.

### Suggested annotations

| Platform | Location (path, check exactly) | Annotation name | PII |
|---|---|---|---|
| TikTok | `/user_data_tiktok.json/Your Activity/Watch History/VideoList/[]` | Watched video | no |
| TikTok | `…/Your Activity/Searches/SearchList/[]/SearchTerm` | Search term | no |
| TikTok | `…/Likes and Favorites/Like List/ItemFavoriteList/[]` | Liked video | no |
| TikTok | `…/Your Activity/Login History/LoginHistoryList/[]/IP` | Login IP address | yes |
| TikTok | `…/Ads and data/Off TikTok Activity/OffTikTokActivityDataList/[]` | Off-platform activity event | no |
| TikTok | `…/Direct Message/Direct Messages/ChatHistory/Chat History with {*}/[]/Content` | Direct message text | yes |
| TikTok | `…/Profile And Settings/Profile Info/ProfileMap/emailAddress` | Account e-mail address | yes |
| Instagram | `/your_instagram_activity/likes/liked_posts.json/[]` | Liked post | no |
| Instagram | `/logged_information/recent_searches/word_or_phrase_searches.json/searches_keyword/[]` | Keyword search | no |
| Instagram | `/your_instagram_activity/messages/inbox/{*}/message_1.json/messages/[]/content` | Direct message text | yes |
| Instagram | `/ads_information/ads_and_topics/ads_viewed.json/[]` | Ad viewed | no |
| Instagram | `/connections/followers_and_following/following.json/relationships_following/[]` | Account followed | no |
| Facebook | `/your_facebook_activity/comments_and_reactions/likes_and_reactions_1.json/[]` | Reaction to a post | no |
| Facebook | `/your_facebook_activity/comments_and_reactions/comments.json/comments_v2/[]` | Comment written | no |
| Facebook | `/logged_information/search/your_search_history.json/searches_v2/[]` | Search | no |
| Facebook | `/apps_and_websites_off_of_facebook/your_activity_off_meta_technologies.json/[]` | Off-Meta activity event | no |
| Facebook | `/security_and_login_information/logins_and_logouts.json/{*}/[]` | Login or logout | no |

The Facebook paths `…/logins_and_logouts.json/{*}` and similar show the parser bug in `08-known-issues-and-open-questions.md`. Keep them as they come out of the parser; do not work around the bug in `seed_demo`.

### Seeded vocabulary (from migration `representations/0002_seed_vocabularies`)

| Vocabulary | Terms (slugs) |
|---|---|
| Actor types | `user`, `other-user`, `platform` |
| Activity types | `added`, `asked`, `blocked`, `created`, `followed`, `joined`, `listened`, `opened`, `responded`, `searched`, `updated`, `viewed` |
| Object types | `audio`, `collection`, `event`, `image`, `note`, `object`, `person`, `profile`, `video` |
| Metadata roles | `applies-to`, `author`, `context`, `duration`, `identifier`, `name`, `value`, `when` |

There is no "liked" or "reacted" activity. For likes and reactions, either:

- create a suggested (unapproved) term "liked" from the demo user, which shows the vocabulary suggestion feature; or
- map to the closest term and explain in the note.

Record the choice in the build decision log.

### Suggested representations

| Platform | List item | Pattern | Slots | Metadata links |
|---|---|---|---|---|
| TikTok | Watch History `VideoList/[]` | activity | user · viewed · video | `Date` (when), `Link` (identifier) |
| TikTok | `SearchList/[]` | activity | user · searched · object | `Date` (when), `SearchTerm` (value) |
| Instagram | `liked_posts.json/[]` | activity | user · liked (suggested term) · image | `timestamp` (when) |
| Instagram | `following.json/relationships_following/[]` | activity | user · followed · profile | `title` (name), timestamp (when) |
| Facebook | `comments.json/comments_v2/[]` | activity | user · created · note | `timestamp` (when) |
| Facebook | `your_search_history.json/searches_v2/[]` | activity | user · searched · object | `timestamp` (when) |

These give the concept view (M1) and comparison (M4) real cross-platform concepts: "viewed video", "searched", "followed profile" and so on.
