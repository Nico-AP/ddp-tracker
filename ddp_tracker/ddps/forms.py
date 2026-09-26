from typing import Any

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import filesizeformat

from ddp_tracker.ddps.models import LANGUAGES, Upload

# offered first in the language picker; everything else follows, sorted by name
COMMON_LANGUAGES = ("en", "de", "fr", "it", "es", "pt", "nl")


def language_choices() -> list[tuple[str, Any]]:
    """ "Unknown", then the common languages, then all others by name (as <optgroup>s)."""
    names = dict(LANGUAGES)
    common = [(code, names[code]) for code in COMMON_LANGUAGES if code in names]
    others = sorted(
        ((code, name) for code, name in LANGUAGES if code not in COMMON_LANGUAGES),
        key=lambda choice: str(choice[1]),
    )
    return [("", "Unknown"), ("Common", common), ("All languages", others)]


class UploadForm(forms.ModelForm):
    file = forms.FileField(
        help_text="The DDP as downloaded from the platform: a zip, or a single JSON / CSV file."
    )

    class Meta:
        model = Upload
        fields = ["platform", "requested_at", "request_mode", "language"]
        widgets = {"requested_at": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        language, mode = self.fields["language"], self.fields["request_mode"]
        assert isinstance(language, forms.ChoiceField)
        assert isinstance(mode, forms.ChoiceField)
        language.choices = language_choices()
        mode.choices = [("", "Unknown"), *Upload.RequestMode.choices]

    def clean_file(self) -> UploadedFile:
        file = self.cleaned_data["file"]
        if file.size > settings.DDP_MAX_UPLOAD_SIZE:
            msg = f"The file is larger than {filesizeformat(settings.DDP_MAX_UPLOAD_SIZE)}."
            raise forms.ValidationError(msg)
        return file
