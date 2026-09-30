from functools import partial

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from ddp_tracker.ddps.models import PathRule, Platform, Upload
from ddp_tracker.ddps.tasks import renormalize_platform


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ["file_name", "platform", "requested_at", "language", "status", "created_at"]
    list_filter = ["platform", "status", "language"]
    readonly_fields = [
        "document",
        "source_sha256",
        "size_bytes",
        "parser_version",
        "parsed_at",
        "error",
    ]


@admin.register(PathRule)
class PathRuleAdmin(admin.ModelAdmin):
    """Saving a rule re-normalizes its platform's stored uploads in the background; deleting one
    can't undo renames (``schemas/renormalize.py``).
    """

    list_display = ["pattern", "kind", "platform", "created_by", "created_at"]
    list_filter = ["platform", "kind"]
    search_fields = ["pattern"]
    readonly_fields = ["created_by", "created_at"]

    def save_model(
        self, request: HttpRequest, obj: PathRule, form: ModelForm, change: bool
    ) -> None:
        if not change and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        platforms = {obj.platform_id}
        if change and "platform" in form.changed_data:
            platforms.add(form.initial["platform"])
        for platform in platforms:
            transaction.on_commit(partial(renormalize_platform.enqueue, platform))
        self.message_user(
            request, "The platform's stored uploads are re-normalized in the background."
        )

    def delete_model(self, request: HttpRequest, obj: PathRule) -> None:
        super().delete_model(request, obj)
        self._deleted(request)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[PathRule]) -> None:
        super().delete_queryset(request, queryset)
        self._deleted(request)

    def _deleted(self, request: HttpRequest) -> None:
        self.message_user(
            request,
            "Uploads parsed from now on no longer use it; stored ones keep their renamed paths.",
            messages.WARNING,
        )
