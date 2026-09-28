import copy
from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_POST

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import REPRESENTATION_FIELDS, ProposalError, submit
from ddp_tracker.representations.forms import (
    SUBJECTS,
    BaseMetadataFormSet,
    DescribeForm,
    MetadataFormSet,
    NewRepresentationForm,
    RepresentationForm,
    RepresentForm,
    SuggestTermForm,
)
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.representations.services import suggest_term
from ddp_tracker.schemas.models import ITEM, Location
from ddp_tracker.users.auth import signed_in_user

_SLOTS = ("actor", "activity", "object", "target")
_SUBJECTS: list[str] = [subject.value for subject in RepresentationMetadata.Subject]


def _representations() -> QuerySet[Representation]:
    return Representation.objects.select_related(*_SLOTS)


def representation_list(request: HttpRequest) -> HttpResponse:
    representations = _representations().prefetch_related(
        "annotations__platform", "metadata_links__annotation__platform"
    )
    rows = []
    for representation in representations:
        annotations = [
            *representation.annotations.all(),
            *(link.annotation for link in representation.metadata_links.all()),
        ]
        rows.append(
            {
                "representation": representation,
                "platforms": sorted({annotation.platform.name for annotation in annotations}),
                "links": len(annotations),
            }
        )
    return render(request, "representations/representation_list.html", {"rows": rows})


def representation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    representation = get_object_or_404(_representations(), pk=pk)
    represented = representation.annotations.select_related("platform").order_by(
        "platform__name", "name"
    )
    links = list(
        representation.metadata_links.select_related("annotation__platform", "role").order_by(
            "role__name", "annotation__name"
        )
    )
    # the matrix: one row per (subject, role), one column per platform
    platforms = sorted(
        {a.platform for a in represented} | {link.annotation.platform for link in links},
        key=lambda platform: platform.name,
    )
    cells: dict[tuple[str, int], dict[int, list[RepresentationMetadata]]] = defaultdict(
        lambda: defaultdict(list)
    )
    roles = {}
    for link in links:
        cells[link.subject, link.role_id][link.annotation.platform_id].append(link)
        roles[link.role_id] = link.role
    matrix = [
        {
            "subject": subject,
            "role": roles[role_id],
            "cells": [by_platform.get(platform.pk, []) for platform in platforms],
        }
        for (subject, role_id), by_platform in sorted(
            cells.items(), key=lambda item: (_SUBJECTS.index(item[0][0]), roles[item[0][1]].name)
        )
    ]
    context = {
        "representation": representation,
        "represented": represented,
        "platforms": platforms,
        "matrix": matrix,
    }
    context["open_suggestions"] = representation.proposals.filter(
        status=Proposal.Status.OPEN
    ).count()
    return render(request, "representations/representation_detail.html", context)


def _values(request: HttpRequest) -> dict[str, str]:
    """A representation form's data, as a proposal keeps it (``proposals.services``)."""
    return {field: request.POST.get(field, "") for field in REPRESENTATION_FIELDS}


@login_required
def representation_create(request: HttpRequest) -> HttpResponse:
    """Staff create it; everyone else suggests it (``proposals``)."""
    form = RepresentationForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            proposal = submit(
                signed_in_user(request),
                Proposal.Kind.NEW_REPRESENTATION,
                values=_values(request),
                comment=request.POST.get("comment", ""),
            )
        except ProposalError as error:
            form.add_error(None, str(error))
        else:
            if proposal is not None:
                messages.success(request, "Suggested; staff will review it.")
                return redirect("proposals:mine")
            return redirect(Representation.objects.get(name=form.cleaned_data["name"]))
    return render(request, "representations/representation_create.html", {"form": form})


def representation_details(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX partial: the representation's statement and description (public)."""
    representation = get_object_or_404(_representations(), pk=pk)
    return render(request, "representations/_details.html", {"representation": representation})


@login_required
def representation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX partial: the edit form; a valid POST returns the updated details block."""
    representation = get_object_or_404(_representations(), pk=pk)
    form = RepresentationForm(
        request.POST or None, instance=copy.copy(representation), user=request.user
    )
    if request.method == "POST" and form.is_valid():
        try:
            proposal = submit(
                signed_in_user(request),
                Proposal.Kind.EDIT_REPRESENTATION,
                representation=representation,
                values=_values(request),
                comment=request.POST.get("comment", ""),
            )
        except ProposalError as error:
            form.add_error(None, str(error))
        else:
            representation = get_object_or_404(_representations(), pk=pk)
            context = {"representation": representation, "suggested": proposal is not None}
            return render(request, "representations/_details.html", context)
    context = {"representation": representation, "form": form}
    return render(request, "representations/_representation_form.html", context)


@login_required
@require_POST
def remove_annotation(request: HttpRequest, pk: int, annotation_pk: int) -> HttpResponse:
    representation = get_object_or_404(Representation, pk=pk)
    annotation = get_object_or_404(Annotation, pk=annotation_pk)
    return _removed(
        request, Proposal.Kind.UNREPRESENT, representation=representation, annotation=annotation
    )


@login_required
@require_POST
def remove_link(request: HttpRequest, pk: int) -> HttpResponse:
    metadata = get_object_or_404(RepresentationMetadata, pk=pk)
    return _removed(request, Proposal.Kind.UNDESCRIBE, metadata=metadata)


def _removed(request: HttpRequest, kind: str, **targets: Any) -> HttpResponse:
    try:
        proposal = submit(signed_in_user(request), kind, **targets)
    except ProposalError as error:
        return HttpResponse(f'<p class="muted">{escape(error)}</p>')
    if proposal is not None:
        return HttpResponse('<p class="muted">Suggested; staff will review it.</p>')
    return HttpResponse('<p class="muted">Removed.</p>')


# --- on annotation pages and in the explorer's side panel --------------------------------------


def _changed(annotation: Annotation) -> HttpResponse:
    """A successful change from the modal: close it, and reload the annotation's lists."""
    return HttpResponse(headers={"HX-Trigger": f"representations-changed-{annotation.pk}"})


def annotation_section_context(
    request: HttpRequest, annotation: Annotation, layout: str = "page"
) -> dict[str, Any]:
    """Context of ``_annotation_representations.html`` (also used by the template tag)."""
    return {
        "annotation": annotation,
        "layout": "panel" if layout == "panel" else "page",
        "represents": annotation.representations.select_related(*_SLOTS),
        "describes": annotation.metadata_links.select_related(
            "role", *(f"representation__{slot}" for slot in _SLOTS)
        ),
        "user": request.user,
    }


def annotation_section(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: an annotation's representations (reloaded after a change)."""
    annotation = get_object_or_404(Annotation, pk=pk)
    context = annotation_section_context(request, annotation, request.GET.get("layout", "page"))
    return render(request, "representations/_annotation_representations.html", context)


def location_section(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: the representations of a location's annotation, for the explorer's side panel."""
    location = get_object_or_404(Location.objects.select_related("annotation"), pk=pk)
    if location.annotation is None:
        return HttpResponse('<p class="muted">Assign an annotation first.</p>')
    context = annotation_section_context(request, location.annotation, "panel")
    return render(request, "representations/_annotation_representations.html", context)


def _modal(
    request: HttpRequest,
    annotation: Annotation,
    represent_form: RepresentForm | None = None,
    describe_form: DescribeForm | None = None,
    create_form: NewRepresentationForm | None = None,
    metadata: BaseMetadataFormSet | None = None,
) -> HttpResponse:
    """The "Add representation" dialog: (a) select an existing one, (b) add a new one."""
    labels = dict(RepresentationMetadata.Subject.choices)
    linked = set(annotation.representations.values_list("pk", flat=True))
    existing: dict[str, list[dict[str, Any]]] = {Pattern.ACTIVITY: [], Pattern.OBJECT: []}
    for representation in Representation.objects.filter(pattern__in=list(existing)).order_by(
        "name"
    ):
        subjects = [
            (subject, labels[subject])
            for subject in SUBJECTS[representation.pattern]
            if getattr(representation, f"{subject}_id") is not None
        ]
        existing[representation.pattern].append(
            {
                "representation": representation,
                "linked": representation.pk in linked,
                "subjects": subjects,
            }
        )
    context = {
        "annotation": annotation,
        # a list's annotation: representations usually point at its item ("watched video")
        "item_annotations": Annotation.objects.filter(
            locations__path__endswith=ITEM,
            locations__parent_path__in=annotation.locations.values("path"),
            locations__platform=annotation.platform_id,
        ).distinct(),
        "happened": existing[Pattern.ACTIVITY],
        "exists": existing[Pattern.OBJECT],
        "roles": MetadataRole.for_user(request.user),
        "errors": [
            error
            for form in (represent_form, describe_form)
            if form is not None
            for error in form.non_field_errors()
            + [message for field_errors in form.errors.values() for message in field_errors]
        ],
        "create_form": create_form or NewRepresentationForm(user=request.user),
        "metadata": metadata or _metadata_formset(request, annotation),
    }
    return render(request, "representations/_representation_modal.html", context)


def _metadata_formset(
    request: HttpRequest,
    annotation: Annotation,
    data: Any = None,  # noqa: ANN401 - a QueryDict
) -> BaseMetadataFormSet:
    return MetadataFormSet(
        data,
        prefix="metadata",
        pattern=(data or {}).get("pattern", ""),
        form_kwargs={"user": request.user, "annotation": annotation},
    )


@login_required
def annotation_add(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: the "Add representation" modal."""
    return _modal(request, get_object_or_404(Annotation, pk=pk))


@login_required
@require_POST
def annotation_represent(request: HttpRequest, pk: int) -> HttpResponse:
    annotation = get_object_or_404(Annotation, pk=pk)
    form = RepresentForm(request.POST, annotation=annotation)
    if not form.is_valid():
        return _modal(request, annotation, represent_form=form)
    try:
        submit(
            signed_in_user(request),
            Proposal.Kind.REPRESENT,
            representation=form.cleaned_data["representation"],
            annotation=annotation,
        )
    except ProposalError as error:
        form.add_error(None, str(error))
        return _modal(request, annotation, represent_form=form)
    return _changed(annotation)


@login_required
@require_POST
def annotation_describe(request: HttpRequest, pk: int) -> HttpResponse:
    annotation = get_object_or_404(Annotation, pk=pk)
    form = DescribeForm(request.POST, annotation=annotation, user=request.user)
    if not form.is_valid():
        return _modal(request, annotation, describe_form=form)
    data = form.cleaned_data
    try:
        submit(
            signed_in_user(request),
            Proposal.Kind.DESCRIBE,
            representation=data["representation"],
            annotation=annotation,
            role=data["role"],
            subject=data["subject"],
        )
    except ProposalError as error:
        form.add_error(None, str(error))
        return _modal(request, annotation, describe_form=form)
    return _changed(annotation)


@login_required
@require_POST
def annotation_create(request: HttpRequest, pk: int) -> HttpResponse:
    """A new representation with the annotation as its entity, and any number of metadata links, in one
    go (staff); everyone else suggests it (``proposals``)."""
    annotation = get_object_or_404(Annotation, pk=pk)
    form = NewRepresentationForm(request.POST, user=request.user)
    metadata = _metadata_formset(request, annotation, request.POST)
    if form.is_valid() and metadata.is_valid():
        rows = [
            {
                "subject": link["subject"],
                "role": link["role"].pk,
                "annotation": link["annotation"].pk,
            }
            for link in metadata.links
        ]
        try:
            submit(
                signed_in_user(request),
                Proposal.Kind.NEW_REPRESENTATION,
                annotation=annotation,
                values=_values(request) | {"relation": "represents", "metadata": rows},
            )
        except ProposalError as error:
            form.add_error(None, str(error))
        else:
            return _changed(annotation)
    return _modal(request, annotation, create_form=form, metadata=metadata)


# --- vocabulary --------------------------------------------------------------------------------


def vocabulary(request: HttpRequest) -> HttpResponse:
    return _vocabulary_page(request, SuggestTermForm())


@login_required
@require_POST
def vocabulary_suggest(request: HttpRequest) -> HttpResponse:
    form = SuggestTermForm(request.POST)
    if not form.is_valid():
        return _vocabulary_page(request, form)
    data = form.cleaned_data
    term = suggest_term(form.model, data["name"], data["description"], signed_in_user(request))
    messages.success(request, f"Thanks, “{term}” is suggested and awaits approval.")
    return redirect("representations:vocabulary")


def _vocabulary_page(request: HttpRequest, form: SuggestTermForm) -> HttpResponse:
    sections = [
        ("Actor types", "Who did something.", ActorType, Count("as_actor", distinct=True)),
        ("Activity types", "What happened.", ActivityType, Count("representations")),
        (
            "Object types",
            "What exists or is acted on.",
            ObjectType,
            Count("as_object", distinct=True) + Count("as_target", distinct=True),
        ),
        ("Metadata roles", "What a describing data point says.", MetadataRole, Count("links")),
    ]
    vocabularies = [
        {
            "title": title,
            "lead": lead,
            "terms": model.objects.filter(approved=True).annotate(usage=usage),
            "pending": (
                model.objects.filter(approved=False, created_by=request.user.pk)
                if request.user.is_authenticated
                else model.objects.none()
            ),
            "review_url": reverse(f"admin:representations_{model.__name__.lower()}_changelist")
            + "?approved__exact=0",
            "to_review": model.objects.filter(approved=False).count()
            if request.user.is_staff
            else 0,
        }
        for title, lead, model, usage in sections
    ]
    context = {"vocabularies": vocabularies, "form": form}
    return render(request, "representations/vocabulary.html", context)
