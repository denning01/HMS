"""Registration forms."""

from django import forms
from django.utils import timezone

from .models import Patient


class PatientForm(forms.ModelForm):
    """The Registration form from the specification, plus its recommended fields."""

    class Meta:
        model = Patient
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "sex",
            "phone_number",
            "residence",
            "national_id",
            "next_of_kin_name",
            "next_of_kin_relationship",
            "next_of_kin_phone",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "next_of_kin_relationship": forms.TextInput(
                attrs={"placeholder": "e.g. spouse, parent, sibling"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-select" if name == "sex" else "form-control"
            field.widget.attrs.setdefault("class", css)

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob > timezone.localdate():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return dob
