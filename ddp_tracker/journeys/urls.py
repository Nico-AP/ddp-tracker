from django.urls import path

from ddp_tracker.journeys import views
from ddp_tracker.journeys.mockups import (
    api,
    changes,
    compare,
    concepts,
    instructions,
    learn,
    moderate,
    roles,
    seeding,
    shortlist,
    snapshots,
)

app_name = "journeys"

urlpatterns = [
    path("", views.index, name="index"),
    path("journeys/<slug:role>/", views.journey, name="journey"),
    path("features/", views.features, name="features"),
    # mock-ups of planned features (mockups/): fictional data, one banner
    path("prototype/concepts/", concepts.concept_list, name="concepts"),
    path("prototype/concepts/<slug:slug>/", concepts.concept_detail, name="concept"),
    path("prototype/shortlist/", shortlist.shortlist, name="shortlist"),
    path("prototype/shortlist/add/", shortlist.add, name="shortlist-add"),
    path("prototype/shortlist/remove/", shortlist.remove, name="shortlist-remove"),
    path("prototype/shortlist/clear/", shortlist.clear, name="shortlist-clear"),
    path("prototype/shortlist/codebook.csv", shortlist.codebook, name="shortlist-codebook"),
    path("prototype/shortlist/blueprint.json", shortlist.blueprint, name="shortlist-blueprint"),
    path("prototype/compare/", compare.compare, name="compare"),
    path("prototype/platforms/<slug:slug>/changes/", changes.changes, name="changes"),
    path("prototype/api/", api.api_overview, name="api"),
    path("prototype/snapshots/", snapshots.snapshots, name="snapshots"),
    path("prototype/request/<slug:slug>/", instructions.request_instructions, name="request"),
    path("prototype/moderate/", moderate.dashboard, name="moderate"),
    path("prototype/moderate/seed/", seeding.seed_sources, name="seed"),
    path("prototype/admin/roles/", roles.roles, name="roles"),
    path("prototype/learn/<slug:slug>/", learn.learn, name="learn"),
]
