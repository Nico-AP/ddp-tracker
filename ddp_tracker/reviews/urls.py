from django.urls import path

from ddp_tracker.reviews import views

app_name = "reviews"

urlpatterns = [
    path("uploads/<int:pk>/review/", views.upload_review, name="review"),
    path(
        "uploads/<int:pk>/review/locations/<int:location_pk>/",
        views.review_location,
        name="location",
    ),
    path(
        "uploads/<int:pk>/review/locations/<int:location_pk>/examples/",
        views.review_add_examples,
        name="add-examples",
    ),
    path("uploads/<int:pk>/review/rows/<int:location_pk>/", views.review_row, name="row"),
]
