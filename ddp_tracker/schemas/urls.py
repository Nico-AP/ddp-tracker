from django.urls import path

from ddp_tracker.schemas import views

app_name = "schemas"

urlpatterns = [
    path("platforms/<slug:slug>/", views.platform_detail, name="platform"),
    path("platforms/<slug:slug>/children/", views.location_children, name="children"),
    path("platforms/<slug:slug>/location/", views.location_detail, name="location"),
    path("uploads/<int:pk>/review/", views.upload_review, name="review"),
    path(
        "uploads/<int:pk>/review/locations/<int:location_pk>/",
        views.review_location,
        name="review-location",
    ),
    path("locations/<int:pk>/triage/", views.triage, name="triage"),
    path("locations/<int:pk>/row/", views.triage_row, name="triage-row"),
    path("locations/<int:pk>/examples/", views.location_examples, name="examples"),
]
