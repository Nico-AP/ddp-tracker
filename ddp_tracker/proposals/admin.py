from django.contrib import admin
from django.http import HttpRequest

from ddp_tracker.proposals.models import Proposal


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    """Read-only: the history of suggestions. Deciding happens in the queues (/proposals/)."""

    list_display = ["kind", "status", "platform", "proposed_by", "created_at", "decided_by"]
    list_filter = ["status", "kind", "platform"]
    search_fields = ["comment", "reason", "location__path", "annotation__name"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Proposal | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Proposal | None = None) -> bool:
        return False
