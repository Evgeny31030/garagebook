from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def latest_vehicle_year():
    return timezone.localdate().year + 1


class Vehicle(models.Model):
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1886),
            MaxValueValidator(latest_vehicle_year),
        ]
    )
    current_mileage = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} {self.make} {self.model}"

class MaintenanceRecord(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )
    date = models.DateField()
    service_type = models.CharField(max_length=100)
    mileage = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cost__gte=0),
                name="maintenance_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(mileage__gte=0),
                name="maintenance_mileage_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.service_type} for {self.vehicle} on {self.date}"
