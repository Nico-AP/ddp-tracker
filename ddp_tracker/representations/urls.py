from django.urls import path

from ddp_tracker.representations import views

app_name = "representations"

urlpatterns = [
    path("", views.representation_list, name="representations"),
    path("new/", views.representation_create, name="create"),
    path("vocabulary/", views.vocabulary, name="vocabulary"),
    path("vocabulary/suggest/", views.vocabulary_suggest, name="suggest"),
    path("<int:pk>/", views.representation_detail, name="representation"),
    path("<int:pk>/details/", views.representation_details, name="details"),
    path("<int:pk>/edit/", views.representation_edit, name="edit"),
    path(
        "<int:pk>/annotations/<int:annotation_pk>/remove/",
        views.remove_annotation,
        name="remove-annotation",
    ),
    path("links/<int:pk>/remove/", views.remove_link, name="remove-link"),
    path("annotations/<int:pk>/section/", views.annotation_section, name="annotation-section"),
    path("annotations/<int:pk>/add/", views.annotation_add, name="add"),
    path("annotations/<int:pk>/represent/", views.annotation_represent, name="represent"),
    path("annotations/<int:pk>/describe/", views.annotation_describe, name="describe"),
    path("annotations/<int:pk>/create/", views.annotation_create, name="create-linked"),
    path("locations/<int:pk>/section/", views.location_section, name="location-section"),
]
