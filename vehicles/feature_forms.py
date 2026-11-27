from django import forms
from django.utils import timezone

from .models import BuildModification, ComponentSchedule, MaintenanceRecord


class ComponentScheduleForm(forms.ModelForm):
    class Meta:
        model = ComponentSchedule
        fields = ["replacements", "interval_km", "interval_days"]
        widgets = {"replacements": forms.CheckboxSelectMultiple}
        labels = {"replacements": "Replacement history", "interval_km": "Service interval (km)", "interval_days": "Service interval (days)"}
        help_texts = {"replacements": "Select all completed records that represent a replacement for this component. Unchecking a record only removes its link, not the service itself.", "interval_km": "Use the manufacturer or workshop interval. Optional.", "interval_days": "Optional. The earliest configured limit wins."}

    def __init__(self, *args, vehicle, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.vehicle = vehicle
        self.fields["replacements"].queryset = vehicle.maintenance_records.filter(status=MaintenanceRecord.Status.COMPLETED).order_by("-date", "-id")
        self.fields["replacements"].label_from_instance = lambda record: f"{record.service_type} — {record.date:%d.%m.%Y} — {record.mileage} km"


class BuildModificationForm(forms.ModelForm):
    class Meta:
        model = BuildModification
        fields = ["name", "category", "status", "cost", "installed_on", "horsepower_before", "horsepower_after", "notes"]
        labels = {"name": "Modification", "cost": "Cost (USD)", "installed_on": "Actual installation date", "horsepower_before": "Measured power before (hp)", "horsepower_after": "Measured power after (hp)"}
        widgets = {"installed_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}
        help_texts = {"cost": "Estimate for planned work; actual cost for installed work. Zero is allowed.", "installed_on": "Required for installed work; leave blank for plans.", "horsepower_before": "Optional actual measurement, not a predicted gain.", "horsepower_after": "Optional actual measurement, not a predicted gain."}

    def __init__(self, *args, vehicle, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.vehicle = vehicle
        self.fields["installed_on"].widget.attrs["max"] = timezone.localdate().isoformat()
