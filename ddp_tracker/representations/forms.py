import copy
from typing import Any, cast

from django import forms
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Model
from django.utils.text import slugify

from ddp_tracker.representations.eligibility import metadata_candidates
from ddp_tracker.representations.models import (
    ActivityType,
    ActorType,
    MetadataRole,
    ObjectType,
    Pattern,
    Representation,
    Vocabulary,
)
from ddp_tracker.schemas.models import Location

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


class DataPointField(forms.ModelChoiceField):
    """A location in a representation's subtree (``offer``): its path from the list on
    (``VideoList/[]/Date``, the path above the list is the same for all), and its annotation if
    it has one."""

    shared = ""  # the path above the list, with its trailing "/"

    def offer(self, anchor: Location) -> None:
        """The data points below ``anchor``, a list's item."""
        self.queryset = metadata_candidates(anchor)
        above_list = (anchor.parent_path or "").rpartition("/")[0]  # "" for a file or the root
        self.shared = f"{above_list}/"

    def label_from_instance(self, obj: Model) -> str:
        assert isinstance(obj, Location)
        path = obj.path.removeprefix(self.shared)
        return f"{path} ({obj.annotation})" if obj.annotation else path


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
    """The representation's own fields in the dialog (its layout)."""

    def __init__(self, *args: Any, user: AnyUser, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        self.fields["pattern"].initial = Pattern.ACTIVITY
        for slot in SLOTS:
            self.fields[slot].widget.attrs["class"] = "form-select"
        for field in ("name", "description", "note"):
            self.fields[field].widget.attrs["class"] = "form-control"


# the slots each pattern shows in the dialog, each with its metadata (what its metadata can describe)
SUBJECTS: dict[str, tuple[str, ...]] = {
    pattern: REQUIRED[pattern] + OPTIONAL.get(pattern, ()) for pattern in Pattern
}

ROW_FIELDS = ("location", "role")


class MetadataRowForm(forms.Form):
    """One metadata link in a slot's section of the dialog: ``location`` (below ``anchor``)
    describes the slot as ``role``. An empty row is skipped; a partly filled one is an error."""

    location = DataPointField(queryset=Location.objects.none(), required=False)
    role = TermField(queryset=MetadataRole.objects.none(), required=False)

    def __init__(self, *args: Any, user: AnyUser, anchor: Location, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        location = self.fields["location"]
        assert isinstance(location, DataPointField)
        location.offer(anchor)
        role = self.fields["role"]
        assert isinstance(role, forms.ModelChoiceField)
        role.queryset = MetadataRole.for_user(user)
        location.widget.attrs["aria-label"] = "Data point"
        role.widget.attrs["aria-label"] = "Role"
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select form-select-sm"

    def clean(self) -> dict[str, Any]:
        super().clean()
        data = self.cleaned_data
        filled = [field for field in ROW_FIELDS if data.get(field)]
        if filled and len(filled) < len(ROW_FIELDS):
            self.add_error(None, "A metadata row needs a data point and a role.")
        return data


class BaseMetadataFormSet(forms.BaseFormSet):
    """One slot's metadata rows (``subject``)."""

    def __init__(self, *args: Any, subject: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.subject = subject

    @property
    def links(self) -> list[tuple[str, MetadataRole, Location]]:
        """The filled rows as ``(subject, role, location)``."""
        return [
            (self.subject, form.cleaned_data["role"], form.cleaned_data["location"])
            for form in self.forms
            if form.is_valid() and all(form.cleaned_data.get(field) for field in ROW_FIELDS)
        ]


# formset_factory builds a subclass of ``formset``; the stubs only know it as a BaseFormSet
MetadataFormSet = cast(
    "type[BaseMetadataFormSet]",
    forms.formset_factory(MetadataRowForm, formset=BaseMetadataFormSet, extra=0),
)


class RepresentationDialog:
    """The representation dialog: its fields, and per slot the metadata rows describing it
    (``sections``, one formset each). For a new representation of ``location`` or an existing
    one (``instance``: its links become the rows, and the rows replace them on saving)."""

    def __init__(
        self,
        data: Any,  # noqa: ANN401 - a QueryDict or None
        *,
        user: AnyUser,
        location: Location,
        instance: Representation | None = None,
    ) -> None:
        self.location = location
        self.instance = instance
        self.form = NewRepresentationForm(
            data, instance=copy.copy(instance) if instance else None, user=user
        )
        # the saved links, only to show (compared with them, an unchanged row would be skipped)
        rows: dict[str, list[dict[str, Any]]] = {subject: [] for subject in SLOTS}
        if instance is not None and data is None:
            for link in instance.metadata_links.order_by("pk"):
                rows[link.subject].append({"location": link.location_id, "role": link.role_id})
        self.sections = {
            subject: MetadataFormSet(
                data,
                prefix=f"metadata-{subject}",
                initial=rows[subject],
                subject=subject,
                form_kwargs={"user": user, "anchor": location},
            )
            for subject in SLOTS
        }

    def slots(self) -> list[tuple[forms.BoundField, BaseMetadataFormSet]]:
        """Each slot's field with its metadata rows, in the dialog's order."""
        return [(self.form[slot], self.sections[slot]) for slot in SLOTS]

    def is_valid(self) -> bool:
        sections = [section.is_valid() for section in self.sections.values()]
        if all(sections):
            # the rows describe the slots: a slot they need can't be left empty
            self.form.instance.described = [subject for subject, _, _ in self.links]
        return self.form.is_valid() and all(sections)

    @property
    def links(self) -> list[tuple[str, MetadataRole, Location]]:
        """The rows of the slots the chosen pattern shows (a hidden slot's rows are dropped)."""
        shown = SUBJECTS.get((self.form.data or {}).get("pattern", ""), ())
        return [link for slot in shown for link in self.sections[slot].links]

    @property
    def rows(self) -> list[dict[str, Any]]:
        """``links`` as a proposal keeps them."""
        return [
            {"subject": subject, "role": role.pk, "location": location.pk}
            for subject, role, location in self.links
        ]
