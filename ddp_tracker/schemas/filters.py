"""Restricting schema views to a subset of uploads (request date, language, root format).

Every descriptive view of the collected schema is computed from the observations of the uploads a
``SchemaFilter`` lets through; the filter travels in the URL query, including HTMX requests.
"""

from dataclasses import dataclass
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
    root_formats = forms.MultipleChoiceField(
        required=False, label="Uploaded as", widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args: Any, platform: Platform, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        registered = platform.uploads.filter(registered_at__isnull=False)
        languages = sorted(set(registered.values_list("language", flat=True)))
        formats = sorted(set(registered.values_list("root_format", flat=True)))
        language_field, format_field = self.fields["languages"], self.fields["root_formats"]
        assert isinstance(language_field, forms.MultipleChoiceField)
        assert isinstance(format_field, forms.MultipleChoiceField)
        language_field.choices = [
            (code, _LANGUAGE_NAMES.get(code, "unknown")) for code in languages
        ]
        format_field.choices = [(value, format_label(value)) for value in formats]


@dataclass(frozen=True)
class SchemaFilter:
    requested_from: date | None = None
    requested_to: date | None = None
    languages: tuple[str, ...] = ()
    root_formats: tuple[str, ...] = ()

    @classmethod
    def from_request(cls, request: HttpRequest, platform: Platform) -> "SchemaFilter":
        form = FilterForm(request.GET, platform=platform)
        if not form.is_valid():
            return cls()
        data = form.cleaned_data
        return cls(
            requested_from=data["requested_from"],
            requested_to=data["requested_to"],
            languages=tuple(data["languages"]),
            root_formats=tuple(data["root_formats"]),
        )

    def uploads(self, platform: Platform) -> QuerySet[Upload]:
        uploads = platform.uploads.filter(registered_at__isnull=False)
        if self.requested_from:
            uploads = uploads.filter(requested_at__gte=self.requested_from)
        if self.requested_to:
            uploads = uploads.filter(requested_at__lte=self.requested_to)
        if self.languages:
            uploads = uploads.filter(language__in=self.languages)
        if self.root_formats:
            uploads = uploads.filter(root_format__in=self.root_formats)
        return uploads

    def observations(self, platform: Platform) -> QuerySet[Observation]:
        return Observation.objects.filter(upload__in=self.uploads(platform))

    @property
    def is_active(self) -> bool:
        return bool(self.requested_from or self.requested_to or self.languages or self.root_formats)

    @property
    def query(self) -> str:
        """The filter as URL parameters (empty when inactive), for links and HTMX requests."""
        params: list[tuple[str, str]] = []
        if self.requested_from:
            params.append(("requested_from", self.requested_from.isoformat()))
        if self.requested_to:
            params.append(("requested_to", self.requested_to.isoformat()))
        params += [("languages", code) for code in self.languages]
        params += [("root_formats", value) for value in self.root_formats]
        return urlencode(params)
