from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "core/index.html", {"project_name": "DDP Tracker"})


def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})
