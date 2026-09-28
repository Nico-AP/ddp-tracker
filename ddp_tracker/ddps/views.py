from collections.abc import Callable

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ddp_tracker.ddps import checks, values
from ddp_tracker.ddps.forms import UploadForm
from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.names import anonymize_file_name
from ddp_tracker.ddps.services import receive
from ddp_tracker.users.auth import signed_in_user
from ddp_tracker.users.models import User


@login_required
def upload_list(request: HttpRequest) -> HttpResponse:
    uploads = Upload.objects.select_related("platform", "uploaded_by")
    return render(request, "ddps/upload_list.html", {"uploads": uploads})


@login_required
def upload_create(request: HttpRequest) -> HttpResponse:
    form = UploadForm(request.POST or None, request.FILES or None, initial=request.GET.dict())
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            upload = form.save(commit=False)
            upload.file_name = anonymize_file_name(form.cleaned_data["file"].name)
            upload.uploaded_by = signed_in_user(request)
            upload.save()
            private_key, public_key = values.new_key_pair()
            receive(upload, form.cleaned_data["file"], public_key)
        response = redirect(upload)
        values.remember(response, upload, private_key)  # only this browser can read them
        return response
    context = {"form": form, "retention_days": settings.DDP_VALUES_RETENTION_DAYS}
    return render(request, "ddps/upload_form.html", context)


@login_required
def upload_detail(request: HttpRequest, pk: int) -> HttpResponse:
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    user = signed_in_user(request)
    context = {
        "upload": upload,
        "duplicates": upload.duplicates(),
        "threshold": settings.DDP_SIMILARITY_THRESHOLD,
        "is_uploader": upload.uploaded_by_id == user.pk,
        "can_approve": checks.can_approve(upload, user),
    }
    return render(request, "ddps/upload_detail.html", context)


@login_required
def upload_status(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX partial, polled while the upload is being parsed."""
    upload = get_object_or_404(Upload, pk=pk)
    if upload.is_finished:
        response = HttpResponse()
        response["HX-Refresh"] = "true"  # reload the page to show the result
        return response
    return render(request, "ddps/_upload_status.html", {"upload": upload})


# --- plausibility: the uploader confirms or discards, staff approve or reject -----------------

_ACTIONS: dict[str, tuple[Callable[[Upload, User], None], str]] = {
    "confirm": (checks.confirm, "Thanks: the upload now waits for an admin's approval."),
    "approve": (checks.approve, "Approved: the upload now counts towards the schema."),
    "reject": (checks.reject, "Rejected: the upload doesn't count towards the schema."),
}


@login_required
@require_POST
def upload_decide(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    """Confirm (uploader), approve or reject (staff) a held upload; see ddps/checks.py."""
    upload = get_object_or_404(Upload, pk=pk)
    user = signed_in_user(request)
    if action == "discard":
        try:
            checks.discard(upload, user)
        except checks.NotAllowedError as exc:
            raise PermissionDenied from exc
        messages.success(request, "The upload was discarded.")
        return redirect("ddps:uploads")

    if action not in _ACTIONS:
        raise PermissionDenied

    act, done = _ACTIONS[action]
    try:
        act(upload, user)
    except checks.NotAllowedError as exc:
        raise PermissionDenied from exc

    messages.success(request, done)
    return redirect(upload)


@staff_member_required
def upload_approvals(request: HttpRequest) -> HttpResponse:
    """Uploads waiting for a staff decision, oldest first."""
    waiting = (
        Upload.objects.filter(plausibility=Upload.Plausibility.AWAITING)
        .select_related("platform", "uploaded_by")
        .order_by("created_at")
    )
    return render(request, "ddps/upload_approvals.html", {"uploads": waiting})


# --- the uploader's own values (ddps/values.py) ------------------------------------------------


@login_required
@require_POST
def upload_forget_values(request: HttpRequest, pk: int) -> HttpResponse:
    """The uploader deletes their values of an upload, and the key to them."""
    upload = get_object_or_404(Upload, pk=pk)
    if upload.uploaded_by_id != signed_in_user(request).pk:
        raise PermissionDenied
    response = redirect(reverse("reviews:review", args=[upload.pk]))
    values.forget(response, upload)
    messages.success(request, "Your values of this upload were deleted.")
    return response


class LogoutView(auth_views.LogoutView):
    """Logging out also deletes the keys to the uploader's values: they become unreadable."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        response = super().post(request, *args, **kwargs)
        values.forget_keys(request, response)
        return response
