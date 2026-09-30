"""M5, the changelog of a platform: what it added, moved, changed and removed from one request
to the next. Computed from the observations of the platform's registered uploads, so with the
demo data (two TikTok packages, six months apart) it is real.
"""

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import find_platform, render_mockup

# --- view (placeholder; task 3.4 replaces it) -----------------------------------------------


def changes(request: HttpRequest, slug: str) -> HttpResponse:
    name, platform = find_platform(slug)
    context = {"platform_name": name, "platform": platform}
    return render_mockup(request, "changes", "journeys/prototype/placeholder.html", context)
