from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_POST

from ddp_tracker.proposals.models import Proposal
from ddp_tracker.proposals.services import REPRESENTATION_FIELDS, ProposalError, submit
from ddp_tracker.representations.eligibility import is_eligible
from ddp_tracker.representations.forms import RepresentationDialog, SuggestTermForm
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Representation,
    RepresentationMetadata,
)
from ddp_tracker.representations.services import suggest_term
from ddp_tracker.schemas.models import Location
from ddp_tracker.users.auth import signed_in_user

_SLOTS = ("actor", "activity", "object", "target")
_SUBJECTS: list[str] = [subject.value for subject in RepresentationMetadata.Subject]


def _representations() -> QuerySet[Representation]:
    return Representation.objects.select_related(
        "location__platform", "location__annotation", *_SLOTS
    )


def _links() -> Prefetch:
    """A representation's metadata links, in the order its pages show them."""
    links = RepresentationMetadata.objects.select_related("role", "location__annotation")
    return Prefetch("metadata_links", queryset=links.order_by("location__path", "role__name"))


def representation_list(request: HttpRequest) -> HttpResponse:
    representations = _representations().annotate(links=Count("metadata_links"))
    return render(
        request,
        "representations/representation_list.html",
        {"representations": representations.order_by("name", "location__platform__name")},
    )


def representation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    representation = get_object_or_404(_representations(), pk=pk)
    # one table per subject, its rows ordered by role
    by_subject: dict[str, list[RepresentationMetadata]] = defaultdict(list)
    links = representation.metadata_links.select_related("role", "location__annotation")
    for link in links.order_by("role__name", "location__path"):
        by_subject[link.subject].append(link)
    context = {
        "representation": representation,
        "described": [
            (subject, by_subject[subject]) for subject in _SUBJECTS if subject in by_subject
        ],
        "open_suggestions": representation.proposals.filter(status=Proposal.Status.OPEN).count(),
    }
    return render(request, "representations/representation_detail.html", context)


def _values(request: HttpRequest) -> dict[str, str]:
    """A representation form's data, as a proposal keeps it (``proposals.services``)."""
    return {field: request.POST.get(field, "") for field in REPRESENTATION_FIELDS}


# --- the dialog (from the side panels and the representation's page) -----------------------------


def _changed(location: Location, proposal: Proposal | None, request: HttpRequest) -> HttpResponse:
    """A change from the dialog: the location's section (and the representation's page) reload.
    Staff's change applied: the dialog closes; a suggestion: the dialog says so."""
    response = (
        HttpResponse() if proposal is None else render(request, "representations/_suggested.html")
    )
    response["HX-Trigger"] = f"representations-changed-{location.pk}"
    return response


def location_section(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: a location's representations (reloaded after a change), or why it has none."""
    location = get_object_or_404(Location, pk=pk)
    context = {
        "location": location,
        "eligible": is_eligible(location),
        "representations": _representations().filter(location=location).prefetch_related(_links()),
    }
    return render(request, "representations/_location_representations.html", context)


def _eligible_location(pk: int) -> Location:
    location = get_object_or_404(Location.objects.select_related("platform"), pk=pk)
    if not is_eligible(location):
        raise Http404
    return location


def _dialog(
    request: HttpRequest, dialog: RepresentationDialog, representation: Representation | None
) -> HttpResponse:
    """Show the dialog, or submit it: a new representation (``representation`` is ``None``) or
    an edit, its metadata rows replacing the links (staff; everyone else suggests it)."""
    if request.method == "POST" and dialog.is_valid():
        values = _values(request) | {"metadata": dialog.rows}
        try:
            if representation is None:
                proposal = submit(
                    signed_in_user(request),
                    Proposal.Kind.NEW_REPRESENTATION,
                    location=dialog.location,
                    values=values,
                )
            else:
                proposal = submit(
                    signed_in_user(request),
                    Proposal.Kind.EDIT_REPRESENTATION,
                    representation=representation,
                    values=values,
                )
        except ProposalError as error:
            dialog.form.add_error(None, str(error))
        else:
            return _changed(dialog.location, proposal, request)
    context = {"dialog": dialog, "location": dialog.location, "representation": representation}
    return render(request, "representations/_representation_modal.html", context)


@login_required
def location_add(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: the dialog for a new representation of the location, and its POST."""
    location = _eligible_location(pk)
    dialog = RepresentationDialog(request.POST or None, user=request.user, location=location)
    return _dialog(request, dialog, None)


@login_required
def representation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX: the dialog for the representation, its metadata included, and its POST."""
    representation = get_object_or_404(_representations(), pk=pk)
    dialog = RepresentationDialog(
        request.POST or None,
        user=request.user,
        location=representation.location,
        instance=representation,
    )
    return _dialog(request, dialog, representation)


@login_required
@require_POST
def representation_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """From the dialog. Deleted on its own page: back to the list."""
    representation = get_object_or_404(_representations(), pk=pk)
    location = representation.location
    on_its_page = request.headers.get("HX-Current-URL", "").endswith(
        representation.get_absolute_url()
    )
    try:
        proposal = submit(
            signed_in_user(request),
            Proposal.Kind.DELETE_REPRESENTATION,
            representation=representation,
            location=location,
        )
    except ProposalError as error:
        return HttpResponse(f'<p class="message message--error">{escape(error)}</p>')
    if proposal is None and on_its_page:
        return HttpResponse(headers={"HX-Redirect": reverse("representations:representations")})
    return _changed(location, proposal, request)


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
