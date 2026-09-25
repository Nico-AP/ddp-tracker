from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import filesizeformat

from ddp_tracker.ddps.models import Upload


class UploadForm(forms.ModelForm):
    file = forms.FileField(
        help_text="The DDP as downloaded from the platform: a zip, or a single JSON / CSV file."
    )

    class Meta:
        model = Upload
        fields = ["platform", "requested_at", "language"]
        widgets = {"requested_at": forms.DateInput(attrs={"type": "date"})}

    def clean_file(self) -> UploadedFile:
        file = self.cleaned_data["file"]
        if file.size > settings.DDP_MAX_UPLOAD_SIZE:
            msg = f"The file is larger than {filesizeformat(settings.DDP_MAX_UPLOAD_SIZE)}."
            raise forms.ValidationError(msg)
        return file
