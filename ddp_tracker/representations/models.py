"""Representations of data points: what a list's items mean (e.g. "user views video"), in the
terms of a shared vocabulary, so platforms can be compared.
"""

from collections import Counter
from typing import Any, ClassVar, Self

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils.text import slugify

from ddp_tracker.schemas.models import Location


class Vocabulary(models.Model):
    """A curated term, extendable without a deploy (seeded by a data migration).

    Relations point at the id. The slug is the stable name code and seeds use to look a term up
    (ids differ between databases), so it is fixed once created; the name can be edited.

    Signed-in users can suggest terms; only approved ones are public and offered to others.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    approved = models.BooleanField(default=False, help_text="Approved by an admin.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects: ClassVar[models.Manager[Self]] = models.Manager()

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.slug:
            msg = f"{self.name!r} gives no slug; set one explicitly."
            raise ValidationError(msg)
        super().save(*args, **kwargs)

    @classmethod
    def for_user(
        cls, user: AbstractBaseUser | AnonymousUser, current: Self | None = None
    ) -> QuerySet[Self]:
        """The terms offered to ``user``: approved ones, their own suggestions, and ``current``
        (a term already in use, so editing doesn't drop it).
        """
        offered = Q(approved=True)
        if user.is_authenticated:
            offered |= Q(created_by=user.pk)
        if current is not None:
            offered |= Q(pk=current.pk)
        return cls.objects.filter(offered)


class ActorType(Vocabulary):
    """Who did something: User (donor), platform …"""


class ActivityType(Vocabulary):
    """What happened: view, listen, follow …"""


class ObjectType(Vocabulary):
    """What exists or is acted on: video, profile, person …"""


class MetadataRole(Vocabulary):
    """What a describing data point says about its subject: when, duration, identifier …"""


class Pattern(models.TextChoices):
    ACTIVITY = "activity", "Something happened"
    OBJECT = "object", "Something exists"
    UNMAPPED = "unmapped", "No confident semantic mapping"


class Representation(models.Model):
    """What a location's entries mean, e.g. "user views video" for each item of a watch history.

    It belongs to one ``location`` (``eligibility.can_have_representation``: for now a list's item
    that is an object); a location can have several. Its ``metadata_links``
    (``RepresentationMetadata``) are locations in that location's subtree that *describe* it,
    each with a role and a subject, one of the slots the representation fills (``Date`` is *when*
    of the activity, ``Link`` the *identifier* of the object, a username the *name* of the actor).
    Unmapped representations fill no slot, so they have no metadata links.

    Annotations play no part: a location can be represented before (or without) being annotated.
    """

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="representations")
    pattern = models.CharField(max_length=20, choices=Pattern)

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    note = models.TextField(blank=True)

    # activity: actor · activity · object (· target); object: object only
    actor = models.ForeignKey(
        ActorType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="as_actor",
    )
    activity = models.ForeignKey(
        ActivityType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="representations",
    )
    object = models.ForeignKey(
        ObjectType, null=True, blank=True, on_delete=models.PROTECT, related_name="as_object"
    )
    target = models.ForeignKey(
        ObjectType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="as_target",
        help_text="Indirect object, e.g. the collection a video is added to.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        pattern=Pattern.ACTIVITY,
                        actor__isnull=False,
                        activity__isnull=False,
                        object__isnull=False,
                    )
                    | models.Q(
                        pattern=Pattern.OBJECT,
                        object__isnull=False,
                        actor__isnull=True,
                        activity__isnull=True,
                        target__isnull=True,
                    )
                    | models.Q(
                        pattern=Pattern.UNMAPPED,
                        actor__isnull=True,
                        activity__isnull=True,
                        object__isnull=True,
                        target__isnull=True,
                    )
                ),
                name="representation_fields_match_pattern",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("representations:representation", args=[self.pk])

    @property
    def statement(self) -> str:
        """The filled slots in order: "user · view · video", "video"; "" if unmapped."""
        slots = (self.actor, self.activity, self.object, self.target)
        return " · ".join(str(term) for term in slots if term is not None)

    # the subjects of the metadata links an edit is about to replace the saved ones with (not a
    # field): validation then checks those instead
    described: list[str] | None = None

    def clean(self) -> None:
        """Keep slots that metadata links describe: emptying one would orphan them."""
        if self.described is not None:
            used = Counter(self.described)
        elif self.pk is not None:
            used = Counter(self.metadata_links.values_list("subject", flat=True))
        else:
            return
        errors = {
            subject: f"{n} metadata link{'s' if n != 1 else ''} describe the {subject}."
            for subject, n in used.items()
            if getattr(self, f"{subject}_id") is None
        }
        if errors:
            raise ValidationError(errors)


class RepresentationMetadata(models.Model):
    class Subject(models.TextChoices):
        # the representation's slots: a link describes one that the representation fills
        ACTOR = "actor", "The actor (who did it)"
        ACTIVITY = "activity", "The activity itself (when, how long)"
        OBJECT = "object", "The object (what it was done to, or what exists)"
        TARGET = "target", "The target (the indirect object)"

    representation = models.ForeignKey(
        Representation, on_delete=models.CASCADE, related_name="metadata_links"
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="metadata_links")
    role = models.ForeignKey(MetadataRole, on_delete=models.PROTECT, related_name="links")
    subject = models.CharField(max_length=20, choices=Subject.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["representation", "location", "role", "subject"],
                name="unique_representation_metadata_link",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.representation} · {self.role}/{self.subject}: {self.location}"

    @property
    def relative_path(self) -> str:
        """The location's path below the representation's (``Date``, ``Author/Name``)."""
        return self.location.path.removeprefix(f"{self.representation.location.path}/")

    def clean(self) -> None:
        if self.subject and getattr(self.representation, f"{self.subject}_id") is None:
            msg = f"This representation has no {self.subject}."
            raise ValidationError({"subject": msg})
        if self.location_id is not None and not is_below(
            self.location, self.representation.location
        ):
            msg = "Only data points below the representation's location can describe it."
            raise ValidationError({"location": msg})


def is_below(location: Location, anchor: Location) -> bool:
    """``location`` lies in ``anchor``'s subtree (on the same platform)."""
    return location.platform_id == anchor.platform_id and location.path.startswith(
        f"{anchor.path}/"
    )
