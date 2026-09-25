from django.contrib import admin

from ddp_tracker.ddps.models import Platform, Upload


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
