"""A suggested change to what is curated: annotating locations, editing annotations, and
representations. Only staff decide (``services.accept`` applies it, ``reject`` records why); the
curated models only ever hold approved data. See docs/docs/tracker/concepts.md, "Suggestions
and approval"."""

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import models

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform
from ddp_tracker.representations.models import Representation
from ddp_tracker.schemas.models import Location


class ProposalQuerySet(models.QuerySet["Proposal"]):
    def visible_to(self, user: AbstractBaseUser | AnonymousUser) -> "ProposalQuerySet":
        """The suggestions whose contents ``user`` may see: all for staff (they decide), their
        own otherwise, none when signed out. That one is open is public (the markers)."""
        if not user.is_authenticated:
            return self.none()
        if getattr(user, "is_staff", False):
            return self
        return self.filter(proposed_by=user.pk)


class Proposal(models.Model):
    class Kind(models.TextChoices):
        # a location's annotation
        LINK = "link", "Link to an annotation"
        NEW_ANNOTATION = "new_annotation", "New annotation"
        IGNORE = "ignore", "Not a data point"
        UNASSIGN = "unassign", "Remove the assignment"
        # an annotation
        EDIT_ANNOTATION = "edit_annotation", "Edit the annotation"
        # representations
        NEW_REPRESENTATION = "new_representation", "New representation"
        EDIT_REPRESENTATION = "edit_representation", "Edit the representation"
        DELETE_REPRESENTATION = "delete_representation", "Delete the representation"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUPERSEDED = "superseded", "Superseded"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    comment = models.TextField(blank=True, help_text="Why (from the proposer).")
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="proposals"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_proposals",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, help_text="Why it was rejected or superseded.")

    # what it is about (each kind uses some). SET_NULL: a proposal stays as history when its
    # target goes (an accepted "delete the representation" deletes it). A new representation's
    # location is the one it is for
    platform = models.ForeignKey(
        Platform, null=True, blank=True, on_delete=models.CASCADE, related_name="proposals"
    )
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals"
    )
    annotation = models.ForeignKey(
        Annotation, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals"
    )
    representation = models.ForeignKey(
        Representation, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposals"
    )
    # the proposed fields (an annotation's name/description/note/pii, a representation's form data
    # and its metadata links)
    values = models.JSONField(default=dict, blank=True)
    # the target as it was when proposed: a proposal made on another state is stale
    base = models.JSONField(default=dict, blank=True)

    objects = ProposalQuerySet.as_manager()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["status", "kind"], name="proposal_status_kind")]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.get_status_display().lower()})"

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN
