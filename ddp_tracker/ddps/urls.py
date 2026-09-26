from django.urls import path, re_path

from ddp_tracker.ddps import views

app_name = "ddps"

urlpatterns = [
    path("", views.upload_list, name="uploads"),
    path("new/", views.upload_create, name="upload-create"),
    path("approvals/", views.upload_approvals, name="approvals"),
    path("<int:pk>/", views.upload_detail, name="upload"),
    path("<int:pk>/status/", views.upload_status, name="upload-status"),
    re_path(
        r"^(?P<pk>[0-9]+)/(?P<action>confirm|discard|approve|reject)/$",
        views.upload_decide,
        name="upload-decide",
    ),
]
