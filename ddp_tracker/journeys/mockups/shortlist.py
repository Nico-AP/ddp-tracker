"""M3, the study shortlist: the concepts a study needs, kept in the visitor's session, shown
with their exact paths, and downloaded as a codebook (CSV) or as File Blueprints for the Data
Donation Module (JSON). It is the hand-off from the researcher to the engineer.
"""

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ddp_tracker.journeys.mockups import render_mockup
from ddp_tracker.journeys.mockups.concepts import CONCEPTS_BY_SLUG, Concept, resolve
from ddp_tracker.schemas.models import ITEM

SESSION_KEY = "journeys_shortlist"  # [{"concept": slug, "note": text}] in the visitor's session
MAX_NOTE = 300
EXAMPLE = ("watched-video", "searched", "liked-content")
SOURCE = "DDP Tracker prototype: fictional demo data"
BLUEPRINT_NOTE = (
    "Illustrative only. It follows the fields of a File Blueprint as described by Pfiffner, "
    "Witlox and Friemel (2024), not the import format of the Data Donation Module."
)
COLUMNS = (
    "concept",
    "platform",
    "annotation",
    "path",
    "type",
    "format",
    "personal_data",
    "tz_whos",
    "first_seen",
    "last_seen",
    "note",
    "source",
)


@dataclass(frozen=True)
class Entry:
    concept: Concept
    note: str = ""


@dataclass(frozen=True)
class Row:
    """One data point of the shortlist: a field of a list's item, or a single value."""

    concept: str
    platform: str
    platform_slug: str
    annotation: str
    path: str
    parent: str  # the list's item the field belongs to; "" for a single value
    value_type: str
    value_format: str
    pii: bool
    tz_whos: str
    first_seen: date | None
    last_seen: date | None
    note: str


# --- which concepts: the visitor's own (session) or the ones a shared link names ------------


def stored(request: HttpRequest) -> list[Entry]:
    """The visitor's own shortlist."""
    return [
        Entry(CONCEPTS_BY_SLUG[item["concept"]], item.get("note", ""))
        for item in request.session.get(SESSION_KEY, [])
        if item.get("concept") in CONCEPTS_BY_SLUG
    ]


def shared(request: HttpRequest) -> list[Entry] | None:
    """The shortlist a link names (``?c=…&c=…``), or None if the link names none."""
    slugs = request.GET.getlist("c")
    if not slugs:
        return None
    return [
        Entry(CONCEPTS_BY_SLUG[slug]) for slug in dict.fromkeys(slugs) if slug in CONCEPTS_BY_SLUG
    ]


def _chosen(request: HttpRequest) -> list[Entry]:
    from_link = shared(request)
    return stored(request) if from_link is None else from_link


def _save(request: HttpRequest, entries: list[Entry]) -> None:
    request.session[SESSION_KEY] = [
        {"concept": entry.concept.slug, "note": entry.note} for entry in entries
    ]


# --- the data points, and the two exports -----------------------------------------------------


def rows(entries: list[Entry]) -> list[Row]:
    """The data points of the chosen concepts, on every platform and at every path the
    database knows (an older path is a variant the engineer has to handle)."""
    found: list[Row] = []
    for entry in entries:
        for view in resolve(entry.concept):
            if view.annotation is None:
                continue
            for location in view.locations:
                is_item = location.location.path.endswith(ITEM)
                found += [
                    Row(
                        concept=entry.concept.name,
                        platform=view.name,
                        platform_slug=view.binding.platform,
                        annotation=view.annotation.name,
                        path=field.location.path,
                        parent=location.location.path if is_item else "",
                        value_type=field.profile.main_type,
                        value_format=field.profile.main_format,
                        pii=view.annotation.pii,
                        tz_whos=view.binding.tz_whos,
                        first_seen=field.profile.first_seen,
                        last_seen=field.profile.last_seen,
                        note=entry.note,
                    )
                    for field in location.fields
                ]
    return found


def codebook_csv(found: list[Row]) -> str:
    """The rows as a codebook: one line per data point, with what a study needs to know."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in found:
        writer.writerow(
            [
                row.concept,
                row.platform,
                row.annotation,
                row.path,
                row.value_type,
                row.value_format,
                "yes" if row.pii else "no",
                row.tz_whos,
                row.first_seen or "",
                row.last_seen or "",
                row.note,
                SOURCE,
            ]
        )
    return out.getvalue()


ITEM_KEY = ITEM.removeprefix("/")  # a list's item, as a key of a path: "[]"
_FILE = re.compile(r"\.(json|jsonl|csv|js)$", re.IGNORECASE)


def split_path(path: str) -> tuple[str, list[str]]:
    """A path as the file and the keys inside it: ``/a/b.json/x/[]/y`` gives
    ``("a/b.json", ["x", "[]", "y"])``. Without a file in it: the whole path, no keys."""
    segments = path.strip("/").split("/")
    for index, segment in enumerate(segments):
        if _FILE.search(segment):
            return "/".join(segments[: index + 1]), segments[index + 1 :]
    return "/".join(segments), []


def blueprints(found: list[Row]) -> dict[str, Any]:
    """The rows as File Blueprints: per list (or single value), the file to expect, where the
    list is in it, and the fields to require and keep."""
    groups: dict[tuple[str, str, str], list[Row]] = {}
    for row in found:
        groups.setdefault((row.platform, row.concept, row.parent or row.path), []).append(row)
    items = []
    for (platform, concept, anchor), members in groups.items():
        file, keys = split_path(anchor)
        if keys and keys[-1] == ITEM_KEY:  # a list: its items' fields
            list_at = keys[:-1]
            fields = [member.path.rsplit("/", 1)[1] for member in members]
        else:  # a single value: its key, in the list (or object) that holds it
            list_at = [key for key in keys[:-1] if key != ITEM_KEY]
            fields = keys[-1:]
        items.append(
            {
                "name": f"{platform}: {concept}",
                "platform": members[0].platform_slug,
                "expected_file": file.replace("{*}", "*"),
                "file_format": file.rsplit(".", 1)[-1].lower(),
                "list_at": list_at,
                "required_fields": fields,
                "fields_to_keep": fields,
                "personal_data": members[0].pii,
            }
        )
    return {"prototype": True, "note": BLUEPRINT_NOTE, "generated_by": SOURCE, "blueprints": items}


# --- views -----------------------------------------------------------------------------------


def shortlist(request: HttpRequest) -> HttpResponse:
    """M3: the chosen concepts with their data points, the link to hand over, the downloads."""
    from_link = shared(request)
    entries = stored(request) if from_link is None else from_link
    found = rows(entries)
    query = urlencode([("c", entry.concept.slug) for entry in entries])
    share_url = request.build_absolute_uri(f"{reverse('journeys:shortlist')}?{query}")
    context = {
        "entries": entries,
        "rows": found,
        "is_shared": from_link is not None,
        "query": query,
        "share_url": share_url if entries else "",
        "personal": sum(row.pii for row in found),
        "codebook": codebook_csv(found),
        "blueprint": json.dumps(blueprints(found), indent=2),
        "example_query": urlencode([("c", slug) for slug in EXAMPLE]),
        "has_data": bool(found),
    }
    return render_mockup(request, "shortlist", "journeys/prototype/shortlist.html", context)


def _back(request: HttpRequest) -> HttpResponse:
    """To where the visitor was (``next``), if that is on this site; else to the shortlist."""
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse("journeys:shortlist")
    return redirect(target)


@require_POST
def add(request: HttpRequest) -> HttpResponse:
    """Add concepts to the visitor's shortlist; with a ``note`` field, set their note."""
    slugs = request.POST.getlist("concept")
    if not slugs or any(slug not in CONCEPTS_BY_SLUG for slug in slugs):
        return HttpResponseBadRequest("Unknown concept.")
    entries = {entry.concept.slug: entry for entry in stored(request)}
    for slug in slugs:
        note = entries[slug].note if slug in entries else ""
        if "note" in request.POST:
            note = request.POST["note"].strip()[:MAX_NOTE]
        entries[slug] = Entry(CONCEPTS_BY_SLUG[slug], note)
    _save(request, list(entries.values()))
    names = ", ".join(CONCEPTS_BY_SLUG[slug].name for slug in dict.fromkeys(slugs))
    messages.success(request, f"Added to your shortlist: {names}.")
    return _back(request)


@require_POST
def remove(request: HttpRequest) -> HttpResponse:
    """Take a concept off the visitor's shortlist."""
    slug = request.POST.get("concept", "")
    _save(request, [entry for entry in stored(request) if entry.concept.slug != slug])
    return _back(request)


@require_POST
def clear(request: HttpRequest) -> HttpResponse:
    """Empty the visitor's shortlist."""
    _save(request, [])
    return _back(request)


def codebook(request: HttpRequest) -> HttpResponse:
    """The shortlist as a codebook (CSV), to download."""
    name = "ddp-tracker-codebook-prototype.csv"
    return HttpResponse(
        codebook_csv(rows(_chosen(request))),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def blueprint(request: HttpRequest) -> HttpResponse:
    """The shortlist as File Blueprints for the Data Donation Module (JSON), to download."""
    name = "ddp-tracker-ddm-blueprints-prototype.json"
    return JsonResponse(
        blueprints(rows(_chosen(request))),
        json_dumps_params={"indent": 2},
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
