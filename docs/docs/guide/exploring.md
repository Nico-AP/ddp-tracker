# Exploring platforms

Everything on this page is open to everyone, without an account.

## Choosing a platform

**Explore** in the top menu lists every platform with a few figures: how many data points and
annotations are known, how many uploads count towards it, and when it was last updated. Choose a
platform to open its **explorer**, or its **annotations** to read what its data points mean.

## The explorer

The explorer shows everything collected about a platform's DDPs, combined from all uploads that
count, as a tree.

### Which DDPs you see

Platforms often offer their data in several forms, and the two aren't mixed:

- **Requested as**: the format that was requested from the platform (for example JSON). The
  explorer opens on the most common one; the others are one click away at the top.
- **Uploaded file**: within one request format, whether the upload was a ZIP archive or a
  single file. A second row of choices appears only when both exist.

Below them, **filters** narrow the uploads by the date the DDP was requested and by the language
the account was set to. Everything shown (which fields exist, their types, the figures) is
computed from the matching uploads only.

### Reading the tree

- **Files** come first, one block per file. Inside a file, fields that only group other fields
  are shown as a heading, for example *Ads and data › Off TikTok Activity*.
- **Each row is one data point**: a piece of information with a meaning of its own. It shows the
  name, the kind of value (text, integer, date, link …), examples or its description.
- A **list** and the entries in it share one row, `VideoList[]`. The fields of each entry are
  listed below it, indented.
- **Greyed-out rows** hold something but aren't data points themselves, for example a file that
  couldn't be read, or a group of fields that was always empty.
- The tree is **alphabetical**. Fields whose names differ only in capitalisation, such as
  `TikTok Live` and `Tiktok Live`, sit next to each other.

Types are shown in plain words:

| You see                           | It means                                                          |
|-----------------------------------|-------------------------------------------------------------------|
| text, integer, number, true/false | the kind of value; *(or empty)* if it is sometimes missing        |
| list of objects, list of texts …  | a list, and what its entries are                                  |
| list (always empty so far)        | a list that never had entries in any upload                       |
| group of keys                     | an object that only groups other fields                           |
| folder, archive, media file       | parts of the DDP's file structure                                 |
| unreadable file                   | a file the DDP Tracker couldn't read                              |

The search field keeps the rows whose name or path contain what you type. A selector shows all
data points, only those **missing an annotation**, or only lists of objects **missing a
representation**: handy for finding what still needs work.

### The side panel

Select a row to see everything known about it in the side panel: its description, where it was
found, its type and format, examples of its values, when and how often it has been seen, and
where it sits in its file, shown as a short JSON outline. Technical details are collapsed at the
bottom.

## Annotations

A platform's **annotations** page lists every described data point: its name, its description,
whether it is personal information (**PII**), in how many places it was found and when it was
last seen. An annotation's own page shows all the places it was found (a field can move or be
named differently in another language), with example values. A list's
[representations](representations.md) are in its side panel.
