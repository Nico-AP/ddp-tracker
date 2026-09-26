from typing import Any

from django import template

from ddp_tracker.ddps.models import Upload

register = template.Library()


@register.simple_tag(takes_context=True)
def approvals_waiting(context: dict[str, Any]) -> int:
    """For staff: how many uploads wait for approval (0 for everyone else, without a query)."""
    user = context.get("user")
    if user is None or not user.is_staff:
        return 0
    return Upload.objects.filter(plausibility=Upload.Plausibility.AWAITING).count()
