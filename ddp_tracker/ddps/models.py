from typing import Any

from django.conf import global_settings, settings
from django.db import models
from django.urls import reverse

LANGUAGES = global_settings.LANGUAGES


class Platform(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("schemas:platform", args=[self.slug])


class Upload(models.Model):
    """One uploaded DDP. The file itself is never stored: only its schema document and the
    metadata the uploader provided.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting to be parsed"
        PARSING = "parsing", "Parsing"
        DONE = "done", "Parsed"
        FAILED = "failed", "Failed"

    class FileFormat(models.TextChoices):
        """What the uploader says the DDP is; the form and the parser hold them to it."""

        ZIP = "zip", "ZIP archive"
        JSON = "json", "JSON file"
        CSV = "csv", "CSV file"

    class Plausibility(models.TextChoices):
        """Whether the upload counts towards the public schema (docs/tracker/concepts.md)."""

        PENDING = "pending", "Not checked yet"
        PASSED = "passed", "Counts"
        UNCONFIRMED = "unconfirmed", "Unusual: to be confirmed by the uploader"
        AWAITING = "awaiting", "Waiting for approval"
        APPROVED = "approved", "Counts (approved)"
        REJECTED = "rejected", "Rejected"
        DUPLICATE = "duplicate", "Duplicate"

    class Reason(models.TextChoices):
        FIRST = "first", "The first upload of its platform and format"
        DISSIMILAR = "dissimilar", "Unlike the other uploads of its platform and format"

    class RequestMode(models.TextChoices):
        DL_APP = "DL_APP", "Downloaded in the app"
        DL_BROWSER = "DL_BROWSER", "Downloaded in the browser"
        PAPI = "PAPI", "Downloaded through the Portability API"

    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="uploads")
    requested_at = models.DateField(help_text="When the DDP was requested from the platform.")
    language = models.CharField(
        max_length=16,
        blank=True,
        choices=LANGUAGES,
        help_text="Language the account was set to when the DDP was requested, if known.",
    )
    request_mode = models.CharField(
        max_length=64,
        blank=True,
        choices=RequestMode.choices,
        help_text="How the DDP was requested, if known.",
    )
    file_format = models.CharField(max_length=16, choices=FileFormat.choices, blank=True)
    file_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="uploads"
    )  # TODO: On delete: Set to PK
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    document = models.JSONField(null=True, blank=True)  # ddp_parser schema document
    source_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    parser_version = models.CharField(max_length=32, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)  # added to the collected schema
    # What the upload was as a whole: "zip", or a single file's format ("csv", "json" …)
    root_format = models.CharField(max_length=16, blank=True)

    # plausibility (ddps/checks.py): only uploads that pass, or are approved, get registered
    plausibility = models.CharField(
        max_length=16, choices=Plausibility.choices, default=Plausibility.PENDING
    )
    plausibility_reason = models.CharField(max_length=16, choices=Reason.choices, blank=True)
    similarity = models.FloatField(null=True, blank=True)  # share of known data points, 0 to 1
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_uploads",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["platform", "requested_at"], name="upload_platform_requested"),
            models.Index(fields=["language"], name="upload_language"),
            models.Index(fields=["root_format"], name="upload_root_format"),
        ]

    def __str__(self) -> str:
        return f"{self.platform} · {self.file_name} ({self.requested_at:%Y-%m-%d})"

    def get_absolute_url(self) -> str:
        return reverse("ddps:upload", args=[self.pk])

    @property
    def is_finished(self) -> bool:
        return self.status in {self.Status.DONE, self.Status.FAILED}

    @property
    def warnings(self) -> list[dict[str, Any]]:
        return list((self.document or {}).get("warnings", []))

    @property
    def counts(self) -> bool:
        """Part of the public schema: passed the checks, or approved."""
        return self.plausibility in {self.Plausibility.PASSED, self.Plausibility.APPROVED}

    def duplicates(self) -> "models.QuerySet[Upload]":
        """Other uploads of the exact same file for this platform."""
        if not self.source_sha256:
            return Upload.objects.none()
        return Upload.objects.filter(
            platform=self.platform, source_sha256=self.source_sha256
        ).exclude(pk=self.pk)
