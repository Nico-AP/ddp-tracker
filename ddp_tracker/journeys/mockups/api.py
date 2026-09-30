"""M6, the API overview: what a read-only API could offer to scripts, other tools and language
models. Nothing here exists: the endpoints, the requests and the answers are examples.
"""

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse

from ddp_tracker.journeys.mockups import render_mockup

BASE = "https://tracker.example.org/api/v1"


@dataclass(frozen=True)
class Endpoint:
    anchor: str  # its id on the page
    path: str
    summary: str
    request: str  # an example request
    response: str  # its answer, shortened
    method: str = "GET"


ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        anchor="platforms",
        path="/platforms",
        summary="Every platform, with how much is known about it.",
        request=f"curl {BASE}/platforms",
        response="""[
  {
    "slug": "tiktok",
    "name": "TikTok",
    "uploads": 2,
    "data_points": 190,
    "annotations": 12,
    "last_requested": "2026-09-15"
  }
]""",
    ),
    Endpoint(
        anchor="schema",
        path="/platforms/{slug}/schema",
        summary=(
            "A platform's collected schema: every data point with its path, type, shape and "
            "format. Filters as in the explorer: requested_from, requested_to, language, "
            "request_format."
        ),
        request=f"curl '{BASE}/platforms/tiktok/schema?request_format=json'",
        response="""{
  "platform": "tiktok",
  "request_format": "json",
  "uploads": 2,
  "data_points": [
    {
      "id": 4711,
      "path": "/user_data_tiktok.json/Your Activity/Watch History/VideoList/[]/Date",
      "type": "string",
      "shape": "datetime",
      "format": "%Y-%m-%d %H:%M:%S",
      "first_seen": "2026-09-15",
      "last_seen": "2026-09-15",
      "annotation": null
    }
  ]
}""",
    ),
    Endpoint(
        anchor="profile",
        path="/data-points/{id}",
        summary=(
            "One data point: what was observed (types, formats, how often, since when), its "
            "annotation and its example values."
        ),
        request=f"curl {BASE}/data-points/4711",
        response="""{
  "id": 4711,
  "platform": "tiktok",
  "path": "/user_data_tiktok.json/Your Activity/Watch History/VideoList/[]/Date",
  "formats": {"%Y-%m-%d %H:%M:%S": 1},
  "time_zone_marker": false,
  "tz_whos": "UTC (assumed)",
  "examples": ["2026-09-01 08:15:42"]
}""",
    ),
    Endpoint(
        anchor="annotations",
        path="/annotations",
        summary="Annotations: what data points mean. Filter by platform, or by pii.",
        request=f"curl '{BASE}/annotations?platform=tiktok'",
        response="""[
  {
    "id": 12,
    "platform": "tiktok",
    "name": "Watched video",
    "description": "One video that was shown to the user, with when it was watched.",
    "pii": false,
    "kind": "curator",
    "paths": [
      "/user_data_tiktok.json/Your Activity/Watch History/VideoList/[]",
      "/user_data_tiktok.json/Activity/Video Browsing History/VideoList/[]"
    ]
  }
]""",
    ),
    Endpoint(
        anchor="representations",
        path="/representations",
        summary=(
            "Representations: what lists' items mean in the shared vocabulary, to compare "
            "platforms. Filter by actor, activity or object."
        ),
        request=f"curl '{BASE}/representations?activity=viewed'",
        response="""[
  {
    "platform": "tiktok",
    "name": "Watched a video",
    "statement": {"actor": "user", "activity": "viewed", "object": "video"},
    "of": "/user_data_tiktok.json/Your Activity/Watch History/VideoList/[]",
    "metadata": [
      {"path": "Date", "role": "when", "subject": "activity"},
      {"path": "Link", "role": "identifier", "subject": "object"}
    ]
  }
]""",
    ),
    Endpoint(
        anchor="vocabulary",
        path="/vocabulary",
        summary="The shared vocabulary: actor, activity and object types, and metadata roles.",
        request=f"curl {BASE}/vocabulary",
        response="""{
  "activity_types": [
    {"slug": "viewed", "name": "viewed", "description": "The actor has viewed the object."}
  ],
  "object_types": [{"slug": "video", "name": "video", "description": "A video."}]
}""",
    ),
    Endpoint(
        anchor="explainers",
        path="/platforms/{slug}/explainers",
        summary=(
            "Plain explanations for participants: what a file or a field is, in words a "
            "donation tool can show while someone decides what to donate."
        ),
        request=f"curl '{BASE}/platforms/tiktok/explainers?language=en'",
        response="""[
  {
    "file": "user_data_tiktok.json",
    "field": "Your Activity / Watch History",
    "explainer": "The videos that were shown to you, with the date and time.",
    "personal_data": false
  }
]""",
    ),
)


@dataclass(frozen=True)
class Export:
    name: str
    path: str
    for_whom: str


EXPORTS: tuple[Export, ...] = (
    Export(
        "JSON Schema",
        "/exports/{slug}.schema.json",
        "Validate a package, or generate code from it.",
    ),
    Export(
        "Codebook (CSV)",
        "/exports/{slug}.codebook.csv",
        "One row per data point, for a methods section or a data management plan.",
    ),
    Export(
        "DDM File Blueprints (JSON)",
        "/exports/{slug}.ddm-blueprints.json",
        "File name, required fields and fields to keep, for the Data Donation Module.",
    ),
)

LLMS_TXT = """# DDP Tracker

> What platforms' data download packages contain, what it means, and how it changes.

## API
- [Platforms](https://tracker.example.org/api/v1/platforms): every platform with its figures
- [Schema](https://tracker.example.org/api/v1/platforms/tiktok/schema): a platform's data points
- [Vocabulary](https://tracker.example.org/api/v1/vocabulary): the shared terms

## Docs
- [Concepts](https://tracker.example.org/docs/tracker/concepts/): the definitions
"""

MCP_TOOLS: tuple[tuple[str, str], ...] = (
    ("list_platforms", "The platforms and how much is known about each."),
    ("get_schema", "A platform's data points, with filters."),
    ("explain_data_point", "What one data point means, with examples."),
    ("find_concept", "Where a concept such as Watched a video appears on each platform."),
)

LICENCE = (
    "The code is GPL-3.0. No licence has been chosen yet for the curated knowledge "
    "(annotations, representations, vocabulary); an open one such as CC BY 4.0 would let "
    "others reuse and cite it. This is an open question for the track."
)

# --- view ------------------------------------------------------------------------------------


def api_overview(request: HttpRequest) -> HttpResponse:
    """M6: what a read-only API could offer."""
    context = {
        "base": BASE,
        "endpoints": ENDPOINTS,
        "exports": EXPORTS,
        "llms_txt": LLMS_TXT,
        "mcp_tools": MCP_TOOLS,
        "licence": LICENCE,
    }
    return render_mockup(request, "api", "journeys/prototype/api.html", context)
