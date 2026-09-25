from django.db import models

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.ddps.models import Platform, Upload


class Location(models.Model):
    """A path ever seen in a platform's uploads: identity, tree structure and curation only.

    Everything descriptive (kind, type, shape, format, when and how often it was seen) comes from
    its observations.
    """

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name="locations")
    path = models.TextField()
    # "" is the root's own path, so only NULL can mean "no parent"
    parent_path = models.TextField(null=True, blank=True)  # noqa: DJ001
    position = models.PositiveIntegerField(default=0)  # order among siblings
    # NULL for array items (and the root, whose name is the upload's possibly personal file name)
    name = models.TextField(null=True, blank=True)  # noqa: DJ001 - "" is a valid key
    annotation = models.ForeignKey(
        Annotation, null=True, blank=True, on_delete=models.SET_NULL, related_name="locations"
    )
    ignored = models.BooleanField(default=False, help_text="Not a data point.")
    example_values = models.JSONField(
        default=list, blank=True, help_text="Curated, non-personal example values."
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "path"], name="unique_location_path"),
        ]
        indexes = [models.Index(fields=["platform", "parent_path"], name="location_children")]

    def __str__(self) -> str:
        return f"{self.platform}: {self.path or '/'}"

    @property
    def display_name(self) -> str:
        """Array item nodes have no name; show them as ``[]`` like in their path."""
        return "[]" if self.name is None else (self.name or '""')

    @property
    def default_name(self) -> str:
        """A name for a new annotation: the key, or for array items "<list key> item"."""
        if self.name is not None:
            return self.name
        segments = self.path.split("/")
        return f"{segments[-2]} item" if len(segments) > 1 else self.path


class Observation(models.Model):
    """A location as it appears in one upload: the source of truth for what a location is."""

    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, related_name="observations")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="observations")
    kind = models.CharField(max_length=16)
    # open for annotation in this upload: ddp_parser.is_data_point (docs/tracker/concepts.md)
    is_data_point = models.BooleanField(default=False)
    type = models.CharField(max_length=100, blank=True)  # "string", or a union "null|string"
    shape = models.CharField(max_length=32, blank=True)
    format = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict)  # stats, length, size … (see ddp_parser)
    suggestions = models.JSONField(default=list)  # [{path, reason, score}] for unknown data points

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["upload", "location"], name="unique_observation"),
        ]
        indexes = [models.Index(fields=["location", "upload"], name="observation_location")]

    def __str__(self) -> str:
        return f"{self.location} in upload {self.upload_id}"
