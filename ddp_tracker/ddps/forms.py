import zipfile
from pathlib import Path
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


def looks_like(file_format: str, file: UploadedFile) -> bool:
    """A cheap check that ``file`` plausibly is ``file_format`` (the parser checks the rest)."""
    head = file.read(4096)
    file.seek(0)

    # ZIP check
    if file_format == Upload.FileFormat.ZIP:
        found = zipfile.is_zipfile(file)
        file.seek(0)
        return found

    # Reject binaries
    if b"\x00" in head:  # binary
        return False

    # JSON check
    if file_format == Upload.FileFormat.JSON:
        return head.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] in (b"{", b"[")

    # CSV check
    first_line = head.split(b"\n", 1)[0]
    return any(delimiter in first_line for delimiter in (b",", b";", b"\t", b"|"))


class UploadForm(forms.ModelForm):
    file = forms.FileField(
        help_text="The DDP as downloaded from the platform: a zip, or a single JSON / CSV file.",
        widget=forms.ClearableFileInput(
            attrs={"accept": ",".join(f".{value}" for value in Upload.FileFormat.values)}
        ),
    )

    class Meta:
        model = Upload
        fields = ["platform", "requested_at", "request_mode", "language", "file_format"]
        labels = {"file_format": "What are you uploading?"}
        widgets = {
            "requested_at": forms.DateInput(attrs={"type": "date"}),
            "file_format": forms.RadioSelect,
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        language, mode = self.fields["language"], self.fields["request_mode"]
        assert isinstance(language, forms.ChoiceField)
        assert isinstance(mode, forms.ChoiceField)
        language.choices = language_choices()
        mode.choices = [("", "Unknown"), *Upload.RequestMode.choices]
        file_format = self.fields["file_format"]
        assert isinstance(file_format, forms.ChoiceField)
        file_format.required = True
        file_format.choices = Upload.FileFormat.choices  # radio buttons: no empty choice

    def clean_file(self) -> UploadedFile:
        file = self.cleaned_data["file"]
        if file.size > settings.DDP_MAX_UPLOAD_SIZE:
            msg = f"The file is larger than {filesizeformat(settings.DDP_MAX_UPLOAD_SIZE)}."
            raise forms.ValidationError(msg)
        return file

    def clean(self) -> dict[str, Any]:
        """The file must be what the uploader said it is (extension and first bytes).
        Prevents accidental upload of wrong files.
        """
        super().clean()
        data = self.cleaned_data
        file, file_format = data.get("file"), data.get("file_format")
        if file is None or not file_format:
            return data
        label = Upload.FileFormat(file_format).label
        if Path(file.name).suffix.lower() != f".{file_format}":
            self.add_error("file", f"You chose {label}, but this file isn't a .{file_format}.")
        elif not looks_like(file_format, file):
            self.add_error("file", f"This doesn't look like a {label}.")
        return data
