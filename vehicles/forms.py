from django import forms
from django.utils import timezone

from .models import MaintenanceRecord, Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["make", "model", "year", "current_mileage"]
        labels = {
            "make": "Make",
            "model": "Model",
            "year": "Year",
            "current_mileage": "Current mileage (km)",
        }


class MaintenanceRecordForm(forms.ModelForm):
    """Create either a completed entry or a plan without trusting POST for status."""

    class Meta:
        model = MaintenanceRecord
        fields = ["date", "service_type", "mileage", "cost", "notes"]
        labels = {
            "date": "Service date",
            "service_type": "Service type",
            "mileage": "Mileage at service (km)",
            "cost": "Cost (USD)",
            "notes": "Notes (optional)",
        }
        widgets = {
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "mileage": forms.NumberInput(attrs={"min": "0"}),
            "cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, vehicle=None, mode=MaintenanceRecord.Status.COMPLETED, **kwargs):
        super().__init__(*args, **kwargs)
        if mode not in MaintenanceRecord.Status.values:
            raise ValueError("Invalid maintenance mode")
        self.vehicle = vehicle
        self.mode = mode
        # Validate the intended status and vehicle in model.clean() during
        # ModelForm.is_valid(), before the instance is saved by the view.
        self.instance.status = mode
        if vehicle is not None:
            self.instance.vehicle = vehicle

        if mode == MaintenanceRecord.Status.COMPLETED:
            for field_name in ("date", "mileage", "cost"):
                self.fields[field_name].required = True
            self.fields["date"].widget.attrs["max"] = timezone.localdate().isoformat()
            if vehicle is not None:
                self.fields["mileage"].widget.attrs["max"] = vehicle.current_mileage
                self.fields["mileage"].help_text = (
                    "For an earlier service, enter its actual mileage. "
                    "If higher than the current mileage, update the vehicle first."
                )
        else:
            self.fields["date"].label = "Target date (optional)"
            self.fields["mileage"].label = "Target mileage (km, optional)"
            self.fields["cost"].label = "Estimated cost (USD, optional)"
            self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
            self.fields["date"].help_text = (
                "Choose today or a future date, or leave blank if unknown."
            )
            self.fields["mileage"].help_text = (
                "Target must be at least the vehicle's current mileage. "
                "Leave blank if unknown."
            )
            if vehicle is not None:
                self.fields["mileage"].widget.attrs["min"] = vehicle.current_mileage
            self.fields["cost"].help_text = "Estimates do not count toward money spent."



class CompleteMaintenanceForm(forms.Form):
    date = forms.DateField(
        label="Actual service date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    mileage = forms.IntegerField(
        label="Actual mileage (km)",
        min_value=0,
        widget=forms.NumberInput(attrs={"min": "0"}),
    )
    cost = forms.DecimalField(
        label="Actual cost (USD)",
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
    )

    def __init__(self, *args, vehicle, **kwargs):
        super().__init__(*args, **kwargs)
        self.vehicle = vehicle
        self.fields["date"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["mileage"].widget.attrs["max"] = vehicle.current_mileage
        self.fields["mileage"].help_text = (
            "If the service was performed at a higher mileage, "
            "update the vehicle's current mileage through Edit vehicle first."
        )

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError("Service date cannot be in the future.")
        return value

    def clean_mileage(self):
        value = self.cleaned_data["mileage"]
        if value > self.vehicle.current_mileage:
            raise forms.ValidationError(
                "Actual mileage exceeds the vehicle's current mileage "
                "(%(current)s km). Update the vehicle first.",
                params={"current": self.vehicle.current_mileage},
            )
        return value
