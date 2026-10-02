from django.urls import path

from ddp_tracker.core import views

app_name = "core"

urlpatterns = [
    path("overview/", views.index, name="index"),  # "/" is the journeys' landing page
    path("health/", views.health, name="health"),
    path("favicon.ico", views.favicon, name="favicon"),
]
