from typing import Any

from django import forms

from ddp_tracker.schemas.models import Location


class ExamplesForm(forms.ModelForm):
    example_values = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Example values",
        help_text="One per line. Only made-up or public values, never real personal data.",
    )

    class Meta:
        model = Location
        fields = ["example_values"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.initial["example_values"] = "\n".join(self.instance.example_values)

    def clean_example_values(self) -> list[str]:
        text: str = self.cleaned_data["example_values"]
        return [line.strip() for line in text.splitlines() if line.strip()]
