from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ddp_tracker.ddps.forms import UploadForm
from ddp_tracker.ddps.models import Upload
from ddp_tracker.ddps.services import receive
from ddp_tracker.users.auth import signed_in_user


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
            upload.file_name = form.cleaned_data["file"].name
            upload.uploaded_by = signed_in_user(request)
            upload.save()
            receive(upload, form.cleaned_data["file"])
        return redirect(upload)
    return render(request, "ddps/upload_form.html", {"form": form})


@login_required
def upload_detail(request: HttpRequest, pk: int) -> HttpResponse:
    upload = get_object_or_404(Upload.objects.select_related("platform"), pk=pk)
    context = {"upload": upload, "duplicates": upload.duplicates()}
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
