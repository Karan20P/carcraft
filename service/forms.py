from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin

from .models import Appointment, CustomerCar, ServiceType


class CustomerCarForm(BootstrapFormMixin, forms.ModelForm):
    current_km = forms.IntegerField(min_value=0, label="Current odometer (km)")
    last_service_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional - helps us predict your next service.",
    )
    last_service_km = forms.IntegerField(required=False, min_value=0, label="Odometer at last service (km)")

    class Meta:
        model = CustomerCar
        fields = ("car_model", "year", "registration_no", "fuel")

    def clean_registration_no(self):
        return self.cleaned_data["registration_no"].upper().replace(" ", "")

    def clean(self):
        data = super().clean()
        d, km, now_km = data.get("last_service_date"), data.get("last_service_km"), data.get("current_km")
        if (d is None) != (km is None):
            raise forms.ValidationError("Give both the date and odometer of your last service, or neither.")
        if d and d > timezone.localdate():
            self.add_error("last_service_date", "That date is in the future.")
        if km is not None and now_km is not None and km > now_km:
            self.add_error("last_service_km", "Can't be more than the current odometer.")
        return data


class OdometerForm(BootstrapFormMixin, forms.Form):
    km = forms.IntegerField(min_value=0, label="Odometer today (km)")

    def __init__(self, *args, car=None, **kwargs):
        self.car = car
        super().__init__(*args, **kwargs)

    def clean_km(self):
        km = self.cleaned_data["km"]
        last = self.car.readings.order_by("-date", "-km").first() if self.car else None
        if last and km < last.km:
            raise forms.ValidationError(f"Odometer can't go backwards (last reading {last.km:,} km).")
        return km


class AppointmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("car", "service_type", "date", "slot", "include_bundle", "notes")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["car"].queryset = CustomerCar.objects.filter(owner=user)
        self.fields["service_type"].queryset = ServiceType.objects.all()

    def clean(self):
        data = super().clean()
        date, slot = data.get("date"), data.get("slot")
        if date:
            if date <= timezone.localdate():
                self.add_error("date", "Please book from tomorrow onwards.")
            elif date.weekday() == 6:
                self.add_error("date", "The workshop is closed on Sundays.")
        if date and slot and not Appointment.slot_is_free(date, slot, exclude_pk=self.instance.pk):
            self.add_error("slot", "All service bays are booked for that slot - please choose another.")
        return data


class CompleteJobForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("odometer_km", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["odometer_km"].required = True

    def clean_odometer_km(self):
        km = self.cleaned_data["odometer_km"]
        last = self.instance.car.readings.order_by("-km").first()
        if last and km < last.km:
            raise forms.ValidationError(f"Odometer can't go backwards (last reading {last.km:,} km).")
        return km
