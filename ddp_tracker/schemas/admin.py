from django.contrib import admin

from ddp_tracker.schemas.models import Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["path", "platform", "annotation", "ignored"]
    list_filter = ["platform", "ignored"]
    search_fields = ["path"]
    raw_id_fields = ["annotation"]
