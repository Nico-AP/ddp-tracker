from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from ddp_tracker.ddps.models import Platform


def index(request: HttpRequest) -> HttpResponse:
    platforms = Platform.objects.annotate(
        annotation_count=Count("annotations", distinct=True),
        upload_count=Count(
            "uploads", filter=Q(uploads__registered_at__isnull=False), distinct=True
        ),
    )
    return render(
        request, "core/index.html", {"project_name": "DDP Tracker", "platforms": platforms}
    )


def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: returns 200 if the process is serving requests."""
    return JsonResponse({"status": "ok"})
