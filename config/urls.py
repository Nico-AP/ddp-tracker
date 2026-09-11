from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path, re_path
from django.views.static import serve

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    re_path(
        r"^docs/(?P<path>.*)$", serve, {"document_root": settings.MKDOCS_ROOT, "show_indexes": True}
    ),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls  # Must be imported here

    urlpatterns += debug_toolbar_urls()
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
