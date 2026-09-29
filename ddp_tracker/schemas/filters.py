"""Restricting schema views to a subset of uploads (request date, language, request format,
root format).

The request format is a single choice (the explorer's selector), defaulting to the platform's most
common one. Within it, the root format is one too: a single JSON file and a zip don't share a
tree. It defaults to the most common one among the request format's uploads; ``""`` means all
(the review). The request format is optional when uploading: uploads without one are chosen
with ``UNKNOWN`` (``""`` would mean "all", and vanish from URLs).

Every descriptive view of the collected schema is computed from the observations of the uploads a
``SchemaFilter`` lets through; the filter travels in the URL query, including HTMX requests.
"""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Any
from urllib.parse import urlencode

from django import forms
from django.db.models import QuerySet
from django.http import HttpRequest

from ddp_tracker.ddps.models import LANGUAGES, Platform, Upload
from ddp_tracker.schemas.models import Observation

_LANGUAGE_NAMES = dict(LANGUAGES)

# the request format of uploads that weren't given one (stored as ""), in filters and URLs
UNKNOWN = "unknown"


def format_label(root_format: str) -> str:
    """How an upload's root format is shown: "ZIP archive", "CSV file" …"""
    if root_format == "zip":
        return "ZIP archive"
    return f"{root_format.upper()} file" if root_format else "file"


def request_format_label(request_format: str) -> str:
    """How a request format is shown: "JSON file" …, "Format not provided" for ``UNKNOWN``."""
    return "Format not provided" if request_format == UNKNOWN else format_label(request_format)


def _of_request_format(uploads: QuerySet[Upload], request_format: str) -> QuerySet[Upload]:
    """``uploads`` of ``request_format`` (``UNKNOWN``: those without one; ``""``: all)."""
    if request_format == UNKNOWN:
        return uploads.filter(request_format="")
    if request_format:
        return uploads.filter(request_format=request_format)
    return uploads


class FilterForm(forms.Form):
    requested_from = forms.DateField(
        required=False, label="Requested from", widget=forms.DateInput(attrs={"type": "date"})
    )
    requested_to = forms.DateField(
        required=False, label="to", widget=forms.DateInput(attrs={"type": "date"})
    )
    languages = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)
    request_format = forms.ChoiceField(required=False, widget=forms.HiddenInput)
    root_format = forms.ChoiceField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args: Any, platform: Platform, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        registered = platform.uploads.filter(registered_at__isnull=False)
        languages = sorted(set(registered.values_list("language", flat=True)))
        language_field = self.fields["languages"]
        assert isinstance(language_field, forms.MultipleChoiceField)
        language_field.choices = [
            (code, _LANGUAGE_NAMES.get(code, "unknown")) for code in languages
        ]
        request_field = self.fields["request_format"]
        assert isinstance(request_field, forms.ChoiceField)
        request_field.choices = [
            ("", "all"),
            *((value, request_format_label(value)) for value, _ in request_formats(platform)),
        ]
        root_field = self.fields["root_format"]
        assert isinstance(root_field, forms.ChoiceField)
        roots = sorted(set(registered.values_list("root_format", flat=True)))
        root_field.choices = [("", "all"), *((value, format_label(value)) for value in roots)]


def root_formats(platform: Platform, request_format: str = "") -> list[tuple[str, int]]:
    """The root formats of the platform's counted uploads (of ``request_format``, if given) with
    how many have each, most common first (ties by name)."""
    counted = _of_request_format(
        platform.uploads.filter(registered_at__isnull=False), request_format
    )
    formats = Counter(counted.values_list("root_format", flat=True))
    return sorted(formats.items(), key=lambda pair: (-pair[1], pair[0]))


def request_formats(platform: Platform) -> list[tuple[str, int]]:
    """The platform's request formats with how many counted uploads have each, most common first
    (ties by name); ``UNKNOWN`` for those without one."""
    counted = platform.uploads.filter(registered_at__isnull=False)
    formats = Counter(
        value or UNKNOWN for value in counted.values_list("request_format", flat=True)
    )
    return sorted(formats.items(), key=lambda pair: (-pair[1], pair[0]))


@dataclass(frozen=True)
class SchemaFilter:
    requested_from: date | None = None
    requested_to: date | None = None
    languages: tuple[str, ...] = ()
    request_format: str = ""  # "" all
    root_format: str = ""  # "" all

    @classmethod
    def from_request(cls, request: HttpRequest, platform: Platform) -> "SchemaFilter":
        """The filter in the request; the request format defaults to the most common one, the
        root format to the most common one among the request format's uploads."""
        form = FilterForm(request.GET, platform=platform)
        data = form.cleaned_data if form.is_valid() else {}
        chosen = cls(
            requested_from=data.get("requested_from"),
            requested_to=data.get("requested_to"),
            languages=tuple(data.get("languages", ())),
            request_format=data.get("request_format", ""),
            root_format=data.get("root_format", ""),
        )
        if not chosen.request_format:
            formats = request_formats(platform)
            if formats:
                chosen = replace(chosen, request_format=formats[0][0])
        if not chosen.root_format:
            roots = root_formats(platform, chosen.request_format)
            if roots:
                chosen = replace(chosen, root_format=roots[0][0])
        return chosen

    def uploads(self, platform: Platform) -> QuerySet[Upload]:
        uploads = platform.uploads.filter(registered_at__isnull=False)
        if self.requested_from:
            uploads = uploads.filter(requested_at__gte=self.requested_from)
        if self.requested_to:
            uploads = uploads.filter(requested_at__lte=self.requested_to)
        if self.languages:
            uploads = uploads.filter(language__in=self.languages)
        uploads = _of_request_format(uploads, self.request_format)
        if self.root_format:
            uploads = uploads.filter(root_format=self.root_format)
        return uploads

    def observations(self, platform: Platform) -> QuerySet[Observation]:
        return Observation.objects.filter(upload__in=self.uploads(platform))

    @property
    def is_active(self) -> bool:
        """Dates or languages chosen (the formats are always one of them)."""
        return bool(self.requested_from or self.requested_to or self.languages)

    @property
    def query(self) -> str:
        """The filter as URL parameters (empty when inactive), for links and HTMX requests."""
        return urlencode(self.params)

    @property
    def params(self) -> list[tuple[str, str]]:
        """The filter as ``(name, value)`` pairs, for URLs and hidden form fields."""
        params: list[tuple[str, str]] = []
        if self.requested_from:
            params.append(("requested_from", self.requested_from.isoformat()))
        if self.requested_to:
            params.append(("requested_to", self.requested_to.isoformat()))
        params += [("languages", code) for code in self.languages]
        if self.request_format:
            params.append(("request_format", self.request_format))
        if self.root_format:
            params.append(("root_format", self.root_format))
        return params

    def with_format(self, request_format: str) -> str:
        """The query of this filter with another request format (the selector's links); its root
        format is that request format's default again."""
        return replace(self, request_format=request_format, root_format="").query

    def with_root_format(self, root_format: str) -> str:
        """The query of this filter with another root format (the second selector's links)."""
        return replace(self, root_format=root_format).query
