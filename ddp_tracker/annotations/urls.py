from django.urls import path

from ddp_tracker.annotations import views

app_name = "annotations"

urlpatterns = [
    path("platform/<slug:slug>/", views.annotation_list, name="annotations"),
    path("<int:pk>/", views.annotation_detail, name="annotation"),
    path("<int:pk>/details/", views.annotation_details, name="details"),
    path("<int:pk>/modal/", views.annotation_modal, name="modal"),
    path("<int:pk>/edit/", views.annotation_edit, name="edit"),
    path("locations/<int:pk>/unlink/", views.unlink, name="unlink"),
]
