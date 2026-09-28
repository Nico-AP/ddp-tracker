from django.conf import settings
from django.db import models
from django.urls import reverse

from ddp_tracker.ddps.models import Platform


class Annotation(models.Model):
    """A data point of a platform (e.g. "watched video date") and what is
    known about it.
    """

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name="annotations")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    note = models.TextField(blank=True)
    pii = models.BooleanField(
        "PII", default=False, help_text="Relates to personally identifiable information."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["platform", "name"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "name"], name="unique_annotation_name"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("annotations:annotation", args=[self.pk])
