"""M3, the study shortlist: the concepts a study needs, kept in the visitor's session, shown
with their exact paths, and downloaded as a codebook (CSV) or as File Blueprints for the Data
Donation Module (JSON). It is the hand-off from the researcher to the engineer.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from ddp_tracker.journeys.mockups import render_mockup

# --- views (placeholders; task 3.3 replaces all of them) ------------------------------------


def shortlist(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "shortlist", "journeys/prototype/placeholder.html")


@require_POST
def add(request: HttpRequest) -> HttpResponse:
    return redirect("journeys:shortlist")


@require_POST
def remove(request: HttpRequest) -> HttpResponse:
    return redirect("journeys:shortlist")


@require_POST
def clear(request: HttpRequest) -> HttpResponse:
    return redirect("journeys:shortlist")


def codebook(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "shortlist", "journeys/prototype/placeholder.html")


def blueprint(request: HttpRequest) -> HttpResponse:
    return render_mockup(request, "shortlist", "journeys/prototype/placeholder.html")
