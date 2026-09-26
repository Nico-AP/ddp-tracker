from typing import Any

from django import forms
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Model
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
    """A new representation, linked to the annotation it's created from."""

    relation = forms.ChoiceField(
        choices=[("represents", "This data point is it"), ("describes", "It describes it")],
        widget=forms.RadioSelect,
        initial="represents",
    )
    role = TermField(queryset=MetadataRole.objects.none(), required=False)
    subject = forms.ChoiceField(
        choices=[("", "---------"), *RepresentationMetadata.Subject.choices], required=False
    )

    def __init__(self, *args: Any, user: AnyUser, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        role = self.fields["role"]
        assert isinstance(role, forms.ModelChoiceField)
        role.queryset = MetadataRole.for_user(user)

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        if data.get("relation") == "describes":
            for field in ("role", "subject"):
                if not data.get(field):
                    self.add_error(field, "Required to describe it.")
        return data
