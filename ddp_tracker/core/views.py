import posixpath
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils._os import safe_join
from django.views.static import serve


def index(request: HttpRequest) -> HttpResponse:
    """What the app offers and where to go for it (the platforms are on the Explore page,
    ``schemas.views.platform_list``)."""
    return render(request, "core/index.html", {"project_name": "DDP Tracker"})


def docs(request: HttpRequest, path: str) -> HttpResponseBase:
    """The MkDocs site (``settings.MKDOCS_ROOT``, built into the production image). MkDocs makes
    every page a folder (``tracker/concepts/index.html``) and links to the folder, so a folder
    serves its ``index.html``; without its trailing slash it redirects to it, for the page's
    relative links to resolve."""
    try:
        target = Path(safe_join(settings.MKDOCS_ROOT, posixpath.normpath(path or ".")))
    except SuspiciousFileOperation as error:  # outside the docs
        raise Http404 from error
    if target.is_dir():
        if path and not path.endswith("/"):
            return redirect(request.path + "/")
        path = posixpath.join(path, "index.html")
    return serve(request, path, document_root=str(settings.MKDOCS_ROOT))


def favicon(request: HttpRequest) -> HttpResponseBase:
    """Browsers ask for /favicon.ico where a page doesn't name its icon (e.g. the MkDocs docs).
    Resolved per request: in production the static URL comes from collectstatic's manifest."""
    return redirect(static("img/favicons/favicon.ico"), permanent=True)


def health(request: HttpRequest) -> JsonResponse:
    """Liveness check: returns 200 if the process is serving requests."""
    return JsonResponse({"status": "ok"})
