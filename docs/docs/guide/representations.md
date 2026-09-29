# Representations

Annotations describe what a data point is. **Representations** describe what the entries of a
list *mean*, in a shared vocabulary: each item of a TikTok watch history is "the user watched a
video", and so is each item of a YouTube watch history. That is how platforms can be compared.

A representation belongs to a **list's item whose entries are objects** (an entry with fields,
such as a date and a link), including files that are such a list (a JSON array, a CSV's rows).
One list can have several representations. The item doesn't need an annotation first.

**Representations** in the top menu lists them all, with their platform and the list they
belong to. A representation's page shows which data points describe it.

## Kinds of representations

- **Something happened**: *who · did what · to what*, and optionally *where*. For example: the
  user · watched · a video; the user · added · a video · to a collection; another user ·
  followed · the user.
- **Something exists**: a thing on its own, like a profile.
- **No confident mapping yet**: noted, but not mapped to a concept so far.

The "who" can be **the user** (the person the DDP belongs to), **another user** (for example a
follower) or **the platform** itself.

## Describing a representation

The data points inside the list's entries **describe** a representation, each with a **role**:
TikTok's `Date` is *when* the video was watched, its `Link` *identifies* the video, a follower's
username is the *name* of the other user. Any data point below the item can be used, however
deeply nested.

In a platform's explorer or an upload's review, open a list's row: its side panel has a
**Representations** section. **Add representation** opens a dialog with a section for each part
(actor, activity, object, target): choose the term, and under it, with **+ Add metadata**, the
data points that describe that part, each with its role. **Edit** opens the same dialog for an
existing representation (also on its own page): change it, its metadata included, or delete it.

## The vocabulary

The words used in representations (the kinds of users, activities such as "watched" or
"followed", things such as "video" or "profile", and the roles) form the **vocabulary**, listed on
its own page. Signed-in users can suggest a new term there: you can use your suggested term right
away, and it is shown to others once an admin approves it.

As with annotations, changes by people who aren't staff are
[suggestions](annotating.md#suggestions) until staff decide.
