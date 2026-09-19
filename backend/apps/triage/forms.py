from django import forms

from .models import Vitals


class VitalsForm(forms.ModelForm):
    class Meta:
        model = Vitals
        fields = [
            "systolic_bp",
            "diastolic_bp",
            "pulse_rate",
            "temperature",
            "spo2",
            "respiratory_rate",
            "weight",
            "height",
            "presenting_complaint",
        ]
        widgets = {
            "presenting_complaint": forms.Textarea(attrs={"rows": 3}),
            "temperature": forms.NumberInput(attrs={"step": "0.1"}),
            "weight": forms.NumberInput(attrs={"step": "0.01", "x-model": "weight"}),
            "height": forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 1.72", "x-model": "height"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        systolic = cleaned.get("systolic_bp")
        diastolic = cleaned.get("diastolic_bp")

        if systolic and diastolic and diastolic >= systolic:
            raise forms.ValidationError(
                "Diastolic pressure must be lower than systolic — check the reading."
            )
        return cleaned
