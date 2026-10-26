from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin

from .models import TestDrive


class TestDriveForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TestDrive
        fields = ("date", "time", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.TextInput(attrs={"placeholder": "Anything we should know? (optional)"}),
        }

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date < timezone.localdate():
            raise forms.ValidationError("Please pick a future date.")
        return date
