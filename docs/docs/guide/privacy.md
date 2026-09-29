# Privacy

A DDP holds personal data: your messages, what you watched, who you follow. The DDP Tracker is
built so that it never needs to keep any of it.

## What happens to your file

1. It is stored only until it has been read, then **deleted**, whether reading succeeded or not.
2. What is kept is its **structure**: which files and fields exist, what type their values are
   (text, date, link …), how many there were. Not the values themselves.
3. Its **file name** is stored anonymized, since it can contain your name or username: words
   that identify no one (like "tiktok", "data" or "export") stay, other letters become `x` and
   digits `0`. `tiktok_johndoe_2024-05-01.zip` becomes `tiktok_xxxxxxx_0000-00-00.zip`.

## Your own values

To help you annotate, a few values per data point (up to 5) are kept **for you alone**, so you
can see what a field contains while reviewing your upload:

- Email addresses are masked, also inside texts: `anna@example.com` becomes `axxx@xxxxxxx.xxx`.
- They are encrypted with a key that only the browser you uploaded from holds. Nobody else can
  read them, not even staff, and the database alone doesn't reveal them.
- They are deleted after 3 days, when you delete them yourself (on the review page), or when you
  log out.
- They only become public if you choose to add some of them to a data point's
  [examples](annotating.md#examples).

## What is public

Everything shown in the explorer, on annotation and representation pages, is derived from the
structure alone, plus examples that someone chose to share. Which account uploaded a DDP isn't
shown to other users.

An upload that doesn't count yet may not be a DDP at all, so its field names could contain
anything: only its uploader and staff can [inspect it](uploading.md#inspecting-an-upload-that-doesnt-count-yet).
