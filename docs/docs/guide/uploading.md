# Uploading a DDP

Uploading your DDP adds its structure to what the DDP Tracker knows about the platform, and shows
you what is new, changed or missing in your package compared with earlier ones. You need an
account: log in, then choose **Upload a DDP** in the top menu.

Your file is deleted as soon as it has been read. See [Privacy](privacy.md) for exactly what is
kept.

## Before you upload

Request your data from the platform (usually in its privacy or account settings) and download it
when it is ready. Upload it **as you received it**: don't unpack, rename or edit it. A ZIP archive
is uploaded as a ZIP; a single JSON or CSV file as that file. Files up to 2 GB are accepted.

## The upload form

| Field                    | What to enter                                                                      |
|--------------------------|------------------------------------------------------------------------------------|
| Platform                 | where the DDP comes from                                                           |
| Requested at             | the date you requested the DDP from the platform (not the upload date)             |
| How it was requested     | in the app, in the browser, or through the platform's Portability API, if you know |
| Requested format         | the format you chose when requesting it (for example JSON), if you know            |
| Account language         | the language your account was set to; field names often depend on it               |
| What are you uploading?  | ZIP archive, JSON file or CSV file                                                 |

The request date and language matter: the DDP Tracker compares your upload with the ones
**requested before it**, and exports in different languages can name the same field differently.

## After uploading

Reading the file takes a moment; the upload's page updates by itself. Then the upload is
checked, so that wrong files or spam don't end up in the public overview:

- **Counted right away** if it looks like the platform's other DDPs. It becomes part of the
  platform's explorer, and you can [review it](reviewing.md).
- **Duplicate** if exactly the same file was uploaded before. It is kept, but not counted twice.
- **Waiting for approval** if it is the first DDP of its platform and format: it will be the
  reference for later uploads, so staff check it first.
- **Unusual** if few of its data points are known: less than 30 % match what the platform's DDPs
  usually contain (fields that were only moved or renamed count as a match). You are asked whether
  it really is a DDP of that platform: confirm it (it then waits for approval) or discard it.
- **Failed** if the file couldn't be read, or isn't what you said it was (for example a JSON file
  declared as ZIP).

Staff then **approve** or **reject** waiting uploads. Approved ones count; rejected ones don't.

### Inspecting an upload that doesn't count yet

While an upload waits, you (its uploader) and staff can **inspect** it from its page: its files
and data points, each marked as

- **known**: the platform's DDPs have it at the same place;
- **matched**: it was moved or renamed from a known field (the old name is shown);
- **new**: neither;

plus the **missing** known data points it doesn't have. This is what the "known" share in the
check is based on, and it helps to decide whether the upload is genuine. Only you and staff can
see this page: an unusual upload may not be a DDP at all. Inspecting doesn't add anything to the
public overview.

## Your uploads

**Uploads** in the top menu lists all uploads with their status. From an upload's page you reach
its [review](reviewing.md) once it counts.
