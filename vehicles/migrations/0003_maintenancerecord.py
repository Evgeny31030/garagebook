# Created for GarageBook maintenance feature (Issue #3).
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0002_alter_vehicle_year"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaintenanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("service_type", models.CharField(max_length=100)),
                ("mileage", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ("cost", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("notes", models.TextField(blank=True)),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="maintenance_records", to="vehicles.vehicle")),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="maintenancerecord",
            constraint=models.CheckConstraint(condition=models.Q(cost__gte=0), name="maintenance_cost_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="maintenancerecord",
            constraint=models.CheckConstraint(condition=models.Q(mileage__gte=0), name="maintenance_mileage_nonnegative"),
        ),
    ]
