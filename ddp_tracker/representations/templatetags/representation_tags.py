from typing import Any

from django import template

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.representations.views import annotation_section_context

register = template.Library()


@register.inclusion_tag("representations/_annotation_representations.html", takes_context=True)
def annotation_representations(
    context: dict[str, Any], annotation: Annotation, layout: str = "page"
) -> dict[str, Any]:
    """The annotation's representations: a table (``page``) or a compact list (``panel``)."""
    return annotation_section_context(context["request"], annotation, layout)
