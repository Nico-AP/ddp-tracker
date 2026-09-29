from django.urls import path

from ddp_tracker.representations import views

app_name = "representations"

urlpatterns = [
    path("", views.representation_list, name="representations"),
    path("platform/<slug:slug>/", views.representation_list, name="platform"),
    path("vocabulary/", views.vocabulary, name="vocabulary"),
    path("vocabulary/suggest/", views.vocabulary_suggest, name="suggest"),
    path("<int:pk>/", views.representation_detail, name="representation"),
    path("<int:pk>/edit/", views.representation_edit, name="edit"),
    path("<int:pk>/delete/", views.representation_delete, name="delete"),
    path("locations/<int:pk>/section/", views.location_section, name="location-section"),
    path("locations/<int:pk>/add/", views.location_add, name="add"),
]
