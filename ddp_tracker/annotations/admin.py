from django.contrib import admin

from ddp_tracker.annotations.models import Annotation


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ["name", "platform", "updated_at"]
    list_filter = ["platform"]
    search_fields = ["name", "description"]
