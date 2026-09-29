from django.urls import path, re_path

from ddp_tracker.proposals import views

app_name = "proposals"

urlpatterns = [
    path("annotations/", views.annotation_queue, name="annotations"),
    path("representations/", views.representation_queue, name="representations"),
    path("mine/", views.mine, name="mine"),
    re_path(r"^(?P<pk>[0-9]+)/(?P<action>accept|reject)/$", views.decide, name="decide"),
    path("<int:pk>/withdraw/", views.withdraw_view, name="withdraw"),
    re_path(
        r"^for/(?P<target>location|annotation|representation|location-representations)/"
        r"(?P<pk>[0-9]+)/$",
        views.for_target,
        name="for",
    ),
]
