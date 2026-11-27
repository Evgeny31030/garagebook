from django import forms

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
