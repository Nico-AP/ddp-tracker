from typing import Any

from django import forms

from ddp_tracker.schemas.examples import EXTRACTED, USER_INPUT, of_source, set_examples
from ddp_tracker.schemas.models import Location


class ExamplesForm(forms.Form):
    """A location's examples: the typed ones are edited as text; the extracted ones (found in an
    uploader's file, schemas/examples.py) can only be kept or removed."""

    extracted = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Extracted from uploads",
        help_text="Found in an uploader's file and contributed as is. Uncheck to remove.",
    )
    example_values = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Example values",
        help_text="One per line. Only made-up or public values, never real personal data.",
    )

    def __init__(self, *args: Any, instance: Location, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.instance = instance
        extracted = of_source(instance, EXTRACTED)
        if extracted:
            field = self.fields["extracted"]
            assert isinstance(field, forms.MultipleChoiceField)
            field.choices = [(value, value) for value in extracted]
            self.initial["extracted"] = extracted
        else:
            del self.fields["extracted"]
        self.initial["example_values"] = "\n".join(of_source(instance, USER_INPUT))

    def clean_example_values(self) -> list[str]:
        text: str = self.cleaned_data["example_values"]
        return [line.strip() for line in text.splitlines() if line.strip()]

    def save(self) -> Location:
        extracted = self.cleaned_data.get("extracted", [])
        set_examples(self.instance, extracted, self.cleaned_data["example_values"])
        return self.instance
