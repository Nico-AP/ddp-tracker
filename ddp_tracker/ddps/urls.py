from django.urls import path

from ddp_tracker.ddps import views

app_name = "ddps"

urlpatterns = [
    path("", views.upload_list, name="uploads"),
    path("new/", views.upload_create, name="upload-create"),
    path("<int:pk>/", views.upload_detail, name="upload"),
    path("<int:pk>/status/", views.upload_status, name="upload-status"),
]
