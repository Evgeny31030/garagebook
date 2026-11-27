from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("vehicles", "0004_planned_maintenance")]
    operations = [
        migrations.CreateModel(
            name="ComponentSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("component", models.CharField(choices=[("engine", "Engine oil"), ("transmission", "Transmission"), ("brakes", "Brakes"), ("tires", "Tires"), ("battery", "Battery"), ("cooling", "Cooling system")], max_length=16)),
                ("interval_km", models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("interval_days", models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("last_service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="vehicles.maintenancerecord")),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="component_schedules", to="vehicles.vehicle")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("vehicle", "component"), name="unique_vehicle_component_schedule")]},
        ),
        migrations.CreateModel(
            name="BuildModification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("category", models.CharField(choices=[("engine", "Engine / ECU"), ("exhaust", "Exhaust"), ("suspension", "Suspension"), ("brakes", "Brakes"), ("wheels", "Wheels / tires"), ("body", "Exterior / interior"), ("other", "Other")], default="other", max_length=16)),
                ("status", models.CharField(choices=[("planned", "Planned"), ("installed", "Installed")], default="planned", max_length=10)),
                ("cost", models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2, validators=[django.core.validators.MinValueValidator(0)])),
                ("installed_on", models.DateField(blank=True, null=True)),
                ("horsepower_before", models.PositiveIntegerField(blank=True, null=True)),
                ("horsepower_after", models.PositiveIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="build_modifications", to="vehicles.vehicle")),
            ],
            options={"ordering": ["-id"], "constraints": [models.CheckConstraint(condition=models.Q(cost__gte=0), name="build_cost_nonnegative"), models.CheckConstraint(condition=(models.Q(status="planned", installed_on__isnull=True) | models.Q(status="installed", installed_on__isnull=False, cost__isnull=False)), name="build_status_fields")]},
        ),
    ]
