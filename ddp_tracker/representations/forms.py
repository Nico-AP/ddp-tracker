from typing import Any, cast

from django import forms
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Case, Model, When
from django.utils.text import slugify

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    RepresentationMetadata,
    Vocabulary,
)

type AnyUser = AbstractBaseUser | AnonymousUser

# which slots each pattern fills (the model's check constraint, as form rules)
REQUIRED = {
    Pattern.ACTIVITY: ("actor", "activity", "object"),
    Pattern.OBJECT: ("object",),
    Pattern.UNMAPPED: (),
}
OPTIONAL = {Pattern.ACTIVITY: ("target",)}
SLOTS = ("actor", "activity", "object", "target")

VOCABULARIES: dict[str, type[Vocabulary]] = {
    "actor": ActorType,
    "activity": ActivityType,
    "object": ObjectType,
    "role": MetadataRole,
}


class TermField(forms.ModelChoiceField):
    """A vocabulary term; pending suggestions are marked."""

    def label_from_instance(self, obj: Model) -> str:
        return str(obj) if getattr(obj, "approved", True) else f"{obj} (suggested)"


class RepresentationForm(forms.ModelForm):
    class Meta:
        model = Representation
        fields = ["pattern", "name", "description", "note", *SLOTS]
        widgets = {
            "pattern": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "actor": "Who...",
            "activity": "...did what...",
            "object": "..to/with what.",
        }
        field_classes = dict.fromkeys(SLOTS, TermField)

    def __init__(self, *args: Any, user: AnyUser, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        pattern = self.fields["pattern"]
        assert isinstance(pattern, forms.ChoiceField)
        pattern.choices = Pattern.choices  # radio buttons: no blank "---------" choice
        for slot in SLOTS:
            model = ObjectType if slot == "target" else VOCABULARIES[slot]
            field = self.fields[slot]
            assert isinstance(field, forms.ModelChoiceField)
            field.queryset = model.for_user(user, getattr(self.instance, slot))

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        pattern = data.get("pattern")
        if pattern not in REQUIRED:
            return data
        for slot in REQUIRED[pattern]:
            if not data.get(slot):
                self.add_error(slot, f"Required for {Pattern(pattern).label.lower()}.")
        for slot in SLOTS:  # hidden in the form for this pattern: drop leftovers
            if slot not in REQUIRED[pattern] + OPTIONAL.get(pattern, ()):
                data[slot] = None
        return data


class RepresentForm(forms.Form):
    representation = forms.ModelChoiceField(queryset=Representation.objects.none())

    def __init__(self, *args: Any, annotation: Annotation, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["representation"]
        assert isinstance(field, forms.ModelChoiceField)
        field.queryset = Representation.objects.exclude(annotations=annotation)


class DescribeForm(forms.Form):
    representation = forms.ModelChoiceField(
        queryset=Representation.objects.exclude(pattern=Pattern.UNMAPPED)
    )
    role = TermField(queryset=MetadataRole.objects.none())
    subject = forms.ChoiceField(choices=RepresentationMetadata.Subject.choices)

    def __init__(self, *args: Any, annotation: Annotation, user: AnyUser, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.annotation = annotation
        field = self.fields["role"]
        assert isinstance(field, forms.ModelChoiceField)
        field.queryset = MetadataRole.for_user(user)

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        if not self.errors:
            link = RepresentationMetadata(annotation=self.annotation, **data)
            try:
                link.full_clean()
            except ValidationError as error:
                for field, messages in error.message_dict.items():
                    for message in messages:
                        self.add_error(None if field == "__all__" else field, message)
        return data


class SuggestTermForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[
            ("actor", "Actor type"),
            ("activity", "Activity type"),
            ("object", "Object type"),
            ("role", "Metadata role"),
        ]
    )
    name = forms.CharField(max_length=100)
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), help_text="What the term means, with an example."
    )

    @property
    def model(self) -> type[Vocabulary]:
        return VOCABULARIES[self.cleaned_data["kind"]]

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        if self.errors:
            return data
        slug = slugify(data["name"])
        if not slug:
            self.add_error("name", "Use letters or digits.")
        elif self.model.objects.filter(name__iexact=data["name"]).exists() or (
            self.model.objects.filter(slug=slug).exists()
        ):
            self.add_error("name", "This term exists already (possibly as a suggestion).")
        return data


class NewRepresentationForm(RepresentationForm):
    """A new representation, created from an annotation: that annotation is its entity."""

    def __init__(self, *args: Any, user: AnyUser, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        self.fields["pattern"].initial = Pattern.ACTIVITY
        for slot in SLOTS:
            self.fields[slot].widget.attrs["class"] = "form-select"
        for field in ("name", "description", "note"):
            self.fields[field].widget.attrs["class"] = "form-control"


# the subjects a pattern's representation fills (what its metadata can describe)
SUBJECTS: dict[str, tuple[str, ...]] = {
    Pattern.ACTIVITY: ("actor", "activity", "object", "target"),
    Pattern.OBJECT: ("object",),
    Pattern.UNMAPPED: (),
}


ROW_FIELDS = ("subject", "role", "annotation")


class MetadataRowForm(forms.Form):
    """One metadata link of a new representation: ``annotation`` describes ``subject`` as
    ``role``. An empty row is skipped; a partly filled one is an error."""

    subject = forms.ChoiceField(
        choices=[("", "---------"), *RepresentationMetadata.Subject.choices], required=False
    )
    role = TermField(queryset=MetadataRole.objects.none(), required=False)
    annotation = forms.ModelChoiceField(queryset=Annotation.objects.none(), required=False)

    def __init__(self, *args: Any, user: AnyUser, annotation: Annotation, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        role = self.fields["role"]
        assert isinstance(role, forms.ModelChoiceField)
        role.queryset = MetadataRole.for_user(user)
        choices = self.fields["annotation"]
        assert isinstance(choices, forms.ModelChoiceField)
        # the platform's annotations, the one the dialog is for first
        choices.queryset = Annotation.objects.filter(platform=annotation.platform_id).order_by(
            Case(When(pk=annotation.pk, then=0), default=1), "name"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select form-select-sm"

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        filled = [field for field in ROW_FIELDS if data.get(field)]
        if filled and len(filled) < len(ROW_FIELDS):
            self.add_error(None, "A metadata row needs a subject, a role and an annotation.")
        return data

    @property
    def link(self) -> dict[str, Any] | None:
        """The row as a link (``None`` for an empty row)."""
        data = self.cleaned_data
        if not all(data.get(field) for field in ROW_FIELDS):
            return None
        return {"subject": data["subject"], "role": data["role"], "annotation": data["annotation"]}


class BaseMetadataFormSet(forms.BaseFormSet):
    def __init__(self, *args: Any, pattern: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pattern = pattern

    def clean(self) -> None:
        if any(self.errors):
            return
        filled = SUBJECTS.get(self.pattern, ())
        for link in self.links:
            if link["subject"] not in filled:
                msg = (
                    "No confident mapping has no metadata."
                    if self.pattern == Pattern.UNMAPPED
                    else f"This representation has no {link['subject']}."
                )
                raise ValidationError(msg)

    @property
    def links(self) -> list[dict[str, Any]]:
        return [form.link for form in self.forms if form.is_valid() and form.link]


# formset_factory builds a subclass of ``formset``; the stubs only know it as a BaseFormSet
MetadataFormSet = cast(
    "type[BaseMetadataFormSet]",
    forms.formset_factory(MetadataRowForm, formset=BaseMetadataFormSet, extra=0),
)
