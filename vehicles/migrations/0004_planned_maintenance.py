from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0003_maintenancerecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancerecord",
            name="status",
            field=models.CharField(
                choices=[("completed", "Completed"), ("planned", "Planned")],
                default="completed",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="maintenancerecord",
            name="date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="maintenancerecord",
            name="mileage",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name="maintenancerecord",
            name="cost",
            field=models.DecimalField(
                blank=True, null=True, decimal_places=2, max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AddConstraint(
            model_name="maintenancerecord",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(status="planned")
                    | models.Q(
                        status="completed",
                        date__isnull=False,
                        mileage__isnull=False,
                        cost__isnull=False,
                    )
                ),
                name="maintenance_status_required_fields",
            ),
        ),
    ]
