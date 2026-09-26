from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Representation,
    RepresentationMetadata,
    Vocabulary,
)


@admin.register(ActorType, ActivityType, ObjectType, MetadataRole)
class VocabularyAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "approved", "created_by", "description"]
    list_filter = ["approved"]
    search_fields = ["name", "description"]
    actions = ["approve"]

    @admin.action(description="Approve selected terms")
    def approve(self, request: HttpRequest, queryset: QuerySet[Vocabulary]) -> None:
        count = queryset.update(approved=True)
        self.message_user(request, f"Approved {count} term{'s' if count != 1 else ''}.")

    def get_prepopulated_fields(
        self, request: HttpRequest, obj: Vocabulary | None = None
    ) -> dict[str, Any]:
        return {"slug": ["name"]} if obj is None else {}

    def get_readonly_fields(self, request: HttpRequest, obj: Vocabulary | None = None) -> list[str]:
        # the slug identifies the term: fixed once created
        return ["slug"] if obj is not None else []

    def save_model(
        self, request: HttpRequest, obj: Vocabulary, form: ModelForm, change: bool
    ) -> None:
        if not change and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class MetadataInline(admin.TabularInline):
    model = RepresentationMetadata
    autocomplete_fields = ["annotation"]
    extra = 1


@admin.register(Representation)
class RepresentationAdmin(admin.ModelAdmin):
    list_display = ["name", "pattern", "actor", "activity", "object", "target", "updated_at"]
    list_filter = ["pattern", "activity", "object"]
    search_fields = ["name", "description"]
    filter_horizontal = ["annotations"]
    inlines = [MetadataInline]

    def save_model(
        self, request: HttpRequest, obj: Representation, form: ModelForm, change: bool
    ) -> None:
        if request.user.is_authenticated:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
