from django import forms

from .models import Vehicle


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