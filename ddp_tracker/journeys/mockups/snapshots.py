"""M7, snapshots: dated releases of the knowledge base, so that a paper, a preregistration or a
report can cite a fixed state. The releases, their figures and their DOIs are fictional.
"""

from dataclasses import dataclass
from datetime import date

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup

DOI_PREFIX = "10.0000/fictional.ddp-tracker"  # 10.0000 is not a registered prefix


@dataclass(frozen=True)
class Snapshot:
    version: str
    released: date
    platforms: int
    data_points: int
    annotations: int
    representations: int
    changes: tuple[str, ...]  # what is new since the release before

    @property
    def doi(self) -> str:
        return f"{DOI_PREFIX}.{self.version}"

    @property
    def citation(self) -> str:
        return (
            f"DDP Tracker contributors. ({self.released:%Y}). DDP Tracker knowledge base "
            f"(Version {self.version}) [Data set]. https://doi.org/{self.doi}"
        )

    @property
    def pinned_url(self) -> str:
        return (
            f"https://tracker.example.org/api/v1/snapshots/{self.version}/platforms/tiktok/schema"
        )


SNAPSHOTS: tuple[Snapshot, ...] = (
    Snapshot(
        version="2026.09",
        released=date(2026, 9, 30),
        platforms=4,
        data_points=632,
        annotations=28,
        representations=9,
        changes=(
            "TikTok: the section Activity is now Your Activity; Tiktok Live is new.",
            "Facebook and Instagram: first packages registered.",
            "9 representations added.",
        ),
    ),
    Snapshot(
        version="2026.08",
        released=date(2026, 8, 31),
        platforms=1,
        data_points=152,
        annotations=9,
        representations=2,
        changes=("TikTok: 9 annotations added.",),
    ),
    Snapshot(
        version="2026.07",
        released=date(2026, 7, 31),
        platforms=1,
        data_points=152,
        annotations=0,
        representations=0,
        changes=("No changes.",),
    ),
    Snapshot(
        version="2026.06",
        released=date(2026, 6, 30),
        platforms=1,
        data_points=152,
        annotations=0,
        representations=0,
        changes=("First release: TikTok, from one package requested in March 2026.",),
    ),
)

# --- view ------------------------------------------------------------------------------------


def snapshots(request: HttpRequest) -> HttpResponse:
    """M7: dated releases of the knowledge base, to cite and to pin."""
    context = {"snapshots": SNAPSHOTS, "latest": SNAPSHOTS[0]}
    return render_mockup(request, "snapshots", "journeys/prototype/snapshots.html", context)
