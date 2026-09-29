# Representations

Annotations describe one platform's data points. **Representations** connect them across
platforms: a representation is a concept, such as "a user watched a video", described
independently of any platform and linked to the data points that hold it on each one. That is how
platforms can be compared.

**Representations** in the top menu lists them all. A representation's page shows which
platforms have it, and a table of who records what: for each part of the concept, the data point
that holds it on each platform.

## Kinds of representations

- **Something happened**: *who · did what · to what*, and optionally *where*. For example: the
  user · watched · a video; the user · added · a video · to a collection; another user ·
  followed · the user.
- **Something exists**: a thing on its own, like a profile.
- **No confident mapping yet**: noted, but not mapped to a concept so far.

The "who" can be **the user** (the person the DDP belongs to), **another user** (for example a
follower) or **the platform** itself.

## How data points are linked

A data point can relate to a representation in two ways:

- It **is** the concept: for "the user watched a video", a watched video (an entry in a watch
  history list) on TikTok, and one on YouTube.
- It **describes** part of it, with a **role**: TikTok's `Date` is *when* the video was watched,
  its `Link` *identifies* the video, a follower's username is the *name* of the other user.

You link data points from the annotation dialog's **Add representation**: pick an existing
representation (the data point *is* it, or *describes* one of its parts), or create a new one with
the data point as its concept, and add rows for the data points that describe it.

## The vocabulary

The words used in representations (the kinds of users, activities such as "watched" or
"followed", things such as "video" or "profile", and the roles) form the **vocabulary**, listed on
its own page. Signed-in users can suggest a new term there: you can use your suggested term right
away, and it is shown to others once an admin approves it.

As with annotations, changes by people who aren't staff are
[suggestions](annotating.md#suggestions) until staff decide.
