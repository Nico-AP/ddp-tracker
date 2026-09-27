from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path, re_path
from django.views import defaults as default_views
from django.views.static import serve

from ddp_tracker.ddps.views import LogoutView

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    re_path(
        r"^docs/(?P<path>.*)$",
        serve,
        {"document_root": settings.MKDOCS_ROOT, "show_indexes": True},
        name="docs",
    ),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),  # also forgets value keys
    path("accounts/", include("django.contrib.auth.urls")),
    path("uploads/", include("ddp_tracker.ddps.urls")),
    path("annotations/", include("ddp_tracker.annotations.urls")),
    path("representations/", include("ddp_tracker.representations.urls")),
    path("proposals/", include("ddp_tracker.proposals.urls")),
    path("", include("ddp_tracker.schemas.urls")),
    path("", include("ddp_tracker.reviews.urls")),
    path("", include("ddp_tracker.core.urls")),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
