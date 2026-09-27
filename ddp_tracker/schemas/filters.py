"""Restricting schema views to a subset of uploads (request date, language, root format).

The root format is a single choice (the explorer's selector): a single JSON file and a zip don't
share a tree. It defaults to the platform's most common one; ``""`` means all (the review).

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


def format_label(root_format: str) -> str:
    """How an upload's root format is shown: "ZIP archive", "CSV file" …"""
    if root_format == "zip":
        return "ZIP archive"
    return f"{root_format.upper()} file" if root_format else "file"


class FilterForm(forms.Form):
    requested_from = forms.DateField(
        required=False, label="Requested from", widget=forms.DateInput(attrs={"type": "date"})
    )
    requested_to = forms.DateField(
        required=False, label="to", widget=forms.DateInput(attrs={"type": "date"})
    )
    languages = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)
    root_format = forms.ChoiceField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args: Any, platform: Platform, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        registered = platform.uploads.filter(registered_at__isnull=False)
        languages = sorted(set(registered.values_list("language", flat=True)))
        formats = sorted(set(registered.values_list("root_format", flat=True)))
        language_field, format_field = self.fields["languages"], self.fields["root_format"]
        assert isinstance(language_field, forms.MultipleChoiceField)
        assert isinstance(format_field, forms.ChoiceField)
        language_field.choices = [
            (code, _LANGUAGE_NAMES.get(code, "unknown")) for code in languages
        ]
        format_field.choices = [("", "all"), *((value, format_label(value)) for value in formats)]


def root_formats(platform: Platform) -> list[tuple[str, int]]:
    """The platform's root formats with how many counted uploads have each, most common first
    (ties by name)."""
    counted = platform.uploads.filter(registered_at__isnull=False)
    formats = Counter(counted.values_list("root_format", flat=True))
    return sorted(formats.items(), key=lambda pair: (-pair[1], pair[0]))


@dataclass(frozen=True)
class SchemaFilter:
    requested_from: date | None = None
    requested_to: date | None = None
    languages: tuple[str, ...] = ()
    root_format: str = ""  # "" all

    @classmethod
    def from_request(cls, request: HttpRequest, platform: Platform) -> "SchemaFilter":
        """The filter in the request; the root format defaults to the most common one."""
        form = FilterForm(request.GET, platform=platform)
        data = form.cleaned_data if form.is_valid() else {}
        chosen = cls(
            requested_from=data.get("requested_from"),
            requested_to=data.get("requested_to"),
            languages=tuple(data.get("languages", ())),
            root_format=data.get("root_format", ""),
        )
        if chosen.root_format:
            return chosen
        formats = root_formats(platform)
        return replace(chosen, root_format=formats[0][0]) if formats else chosen

    def uploads(self, platform: Platform) -> QuerySet[Upload]:
        uploads = platform.uploads.filter(registered_at__isnull=False)
        if self.requested_from:
            uploads = uploads.filter(requested_at__gte=self.requested_from)
        if self.requested_to:
            uploads = uploads.filter(requested_at__lte=self.requested_to)
        if self.languages:
            uploads = uploads.filter(language__in=self.languages)
        if self.root_format:
            uploads = uploads.filter(root_format=self.root_format)
        return uploads

    def observations(self, platform: Platform) -> QuerySet[Observation]:
        return Observation.objects.filter(upload__in=self.uploads(platform))

    @property
    def is_active(self) -> bool:
        """Dates or languages chosen (the format is always one of them)."""
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
        if self.root_format:
            params.append(("root_format", self.root_format))
        return params

    def with_format(self, root_format: str) -> str:
        """The query of this filter with another root format (the selector's links)."""
        return replace(self, root_format=root_format).query
