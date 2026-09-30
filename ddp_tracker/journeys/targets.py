"""Links from journey steps into the demo data (``manage.py seed_demo``): the review of the
demo upload, a held upload to inspect, an annotation. A link only exists if the data does and
the visitor may open it; otherwise the step simply does not show it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Upload

type Visitor = AbstractBaseUser | AnonymousUser


@dataclass(frozen=True)
class DemoLink:
    label: str
    url: str


def _tiktok_review(user: Visitor) -> DemoLink | None:
    """The review of the latest TikTok upload that counts: for its uploader and staff."""
    upload = (
        Upload.objects.visible_to(user)
        .filter(platform__slug="tiktok", registered_at__isnull=False)
        .order_by("-requested_at")
        .first()
    )
    if upload is None:
        return None
    url = reverse("reviews:review", args=[upload.pk])
    return DemoLink("Open the review of the demo TikTok upload", url)


def _held_upload(user: Visitor) -> DemoLink | None:
    """An upload that waits for approval: for its uploader and staff to inspect."""
    upload = (
        Upload.objects.visible_to(user)
        .filter(
            plausibility=Upload.Plausibility.AWAITING,
            document__isnull=False,
            registered_at__isnull=True,
        )
        .order_by("created_at")
        .first()
    )
    if upload is None:
        return None
    url = reverse("ddps:upload-inspect", args=[upload.pk])
    return DemoLink("Inspect the held demo upload", url)


def _watched_video(user: Visitor) -> DemoLink | None:
    """TikTok's annotation of a watched video (public)."""
    annotation = Annotation.objects.filter(platform__slug="tiktok", name="Watched video").first()
    if annotation is None:
        return None
    return DemoLink("Read TikTok's annotation Watched video", annotation.get_absolute_url())


_LINKS: dict[str, Callable[[Visitor], DemoLink | None]] = {
    "tiktok-review": _tiktok_review,
    "held-upload": _held_upload,
    "watched-video": _watched_video,
}
DEMO_LINK_KEYS = tuple(_LINKS)


def demo_link(key: str, user: Visitor) -> DemoLink | None:
    """The demo link ``key`` for ``user``, if there is one to show ("" means the step has none)."""
    return _LINKS[key](user) if key else None
