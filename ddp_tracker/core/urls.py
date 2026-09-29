from django.urls import path

from ddp_tracker.core import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health, name="health"),
    path("favicon.ico", views.favicon, name="favicon"),
]
