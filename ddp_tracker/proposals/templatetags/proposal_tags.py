from collections.abc import Iterable
from functools import reduce
from operator import or_

from django import template
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Model, Q

from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import ANNOTATION_KINDS, REPRESENTATION_KINDS, open_for

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


@register.simple_tag
def open_suggestions(
    target: str,
    things: Model | Iterable[Model],
    user: AbstractBaseUser | AnonymousUser | None = None,
) -> int:
    """How many suggestions about ``things`` (one, or several: a list row's list and item) are
    open, as ``proposals:for`` ``target`` lists them. Without ``user``, a public marker (everyone
    sees that one is open); with it, only those ``user`` may see (their own; all for staff)."""
    items = [things] if isinstance(things, Model) else list(things)
    if not items:
        return 0
    about = reduce(or_, (open_for(target, item.pk) for item in items), Q(pk__in=[]))
    proposals = Proposal.objects.visible_to(user) if user is not None else Proposal.objects
    return proposals.filter(about).distinct().count()
