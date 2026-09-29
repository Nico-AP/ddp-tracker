from django.urls import path

from ddp_tracker.schemas import views

app_name = "schemas"

urlpatterns = [
    path("platforms/", views.platform_list, name="platforms"),
    path("platforms/<slug:slug>/", views.platform_detail, name="platform"),
    path("platforms/<slug:slug>/rows/<int:location_pk>/", views.explorer_row, name="row"),
    path("platforms/<slug:slug>/location/", views.location_detail, name="location"),
    path("locations/<int:pk>/triage/", views.triage, name="triage"),
    path("locations/<int:pk>/examples/", views.location_examples, name="examples"),
]
