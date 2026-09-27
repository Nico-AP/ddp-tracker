from django import template

from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import ANNOTATION_KINDS, REPRESENTATION_KINDS

register = template.Library()


@register.simple_tag
def proposals_waiting() -> dict[str, int]:
    """Open suggestions for staff's queues."""
    open_ = Proposal.objects.filter(status=Proposal.Status.OPEN)
    annotations = open_.filter(kind__in=ANNOTATION_KINDS).count()
    representations = open_.filter(kind__in=REPRESENTATION_KINDS).count()
    return {
        "annotations": annotations,
        "representations": representations,
        "total": annotations + representations,
    }
