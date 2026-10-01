# Fictional sample DDPs

Three made-up data download packages for trying out the DDP Tracker locally, created 30 September 2026.

| File | Platform | Files inside | Data points after parsing |
|---|---|---|---|
| `facebook-noorfictional-2026-09-15-AbCdEf12.zip` | Facebook | 40 (JSON plus a few tiny images) | 290 nodes |
| `instagram-noor.fictional-2026-09-15-XyZ12345.zip` | Instagram | 31 (JSON plus a few tiny images) | 298 nodes |
| `tiktok_fictional_2026-09-15.zip` | TikTok | 1 (`user_data_tiktok.json`) | 207 nodes |

## What is real and what is made up

- **Made up:** everything in the values. The persona "Noor Vermeulen", her friends, messages, searches, posts and IDs are invented. E-mail addresses use `example.org`, IP addresses use the documentation ranges reserved for examples (192.0.2.x, 198.51.100.x, 203.0.113.x), and phone numbers are fictional.
- **Modelled on reality:** the structure. Folder names, file names, keys and value formats follow what the public DDP Tracker (ddp-tracker.org) shows for real 2026 exports. Each package is a representative subset, not a full export: real Facebook exports have thousands of data points.
- **Realistic quirks included on purpose:**
  - Meta's text encoding bug, where emoji and accented letters appear garbled;
  - a wrapper folder named like the zip in the Facebook export;
  - message threads in folders named after the chat partner;
  - TikTok chat keys that contain usernames ("Chat History with …");
  - Unix timestamps in seconds and milliseconds;
  - empty sections.

## How to use them

Upload them through the normal upload form in a local DDP Tracker. For all three:

| Field | Value |
|---|---|
| Request date | 15 September 2026 |
| Request mode | Downloaded in the browser |
| Request format | JSON |
| Account language | English |
| File type | ZIP |

Each is the first upload for its platform, so a staff account has to approve it on the Approvals page.

To create the platforms first, add Facebook, Instagram and TikTok in the Django admin (slugs `facebook`, `instagram`, `tiktok`).

## Checked

All three were parsed with the repository's parser, uploaded through the upload form of a local instance, approved and registered. The explorer and review pages loaded without errors.

## Findings from testing

- **Parser: Facebook's `_v2` keys are wrongly treated as variable keys.** Facebook wraps many files in a single key such as `deleted_friends_v2` or `account_accesses_v2`. The parser's "hash-like token" rule (`normalize.py`: letters and digits, at least 16 characters, underscores allowed) matches these, so they are renamed to `{*}`. Paths such as `removed_friends.json/{*}` lose meaningful names. This is probably what the hackathon issue "the tracker anonymizes file paths when repeated values occur" is seeing, and worth reporting to Nico.
- **TikTok chat names are collapsed correctly here** (`Chat History with {*}`) because the package has three chats. With only one chat, the username would stay in the path; see the TikTok issue in the features document.

## Regenerating

`make_sample_ddps.py` recreates the three zips. The random seed is fixed, so the output is identical every time. Run it with Python 3.10 or later, no extra packages:

```
python make_sample_ddps.py output_folder
```
