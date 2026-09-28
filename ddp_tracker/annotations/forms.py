from django import forms

from ddp_tracker.annotations.models import Annotation


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ["name", "description", "note", "pii"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "pii": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
