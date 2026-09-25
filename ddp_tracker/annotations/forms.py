from django import forms

from ddp_tracker.annotations.models import Annotation


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ["name", "description", "note"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }
