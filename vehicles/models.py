from django.core.exceptions import ValidationError
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
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        PLANNED = "planned", "Planned"

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.COMPLETED
    )
    # Planned records can have an unknown target date, mileage and estimated cost.
    # For completed records these are the actual date, mileage and cost.
    date = models.DateField(null=True, blank=True)
    service_type = models.CharField(max_length=100)
    mileage = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
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
            models.CheckConstraint(
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
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.PLANNED:
            # Unknown target date/mileage is valid. Known targets must not
            # already be in the past or behind the vehicle's odometer.
            if self.date is not None and self.date < timezone.localdate():
                errors["date"] = "Planned service date cannot be in the past."
            if (
                self.mileage is not None
                and self.vehicle_id
                and self.mileage < self.vehicle.current_mileage
            ):
                errors["mileage"] = (
                    "Target mileage cannot be below the vehicle's current mileage "
                    f"({self.vehicle.current_mileage} km)."
                )
            if errors:
                raise ValidationError(errors)
            return

        if self.status != self.Status.COMPLETED:
            return

        if self.date is None:
            errors["date"] = "Completed services require an actual date."
        elif self.date > timezone.localdate():
            errors["date"] = "Service date cannot be in the future."

        if self.mileage is None:
            errors["mileage"] = "Completed services require the actual mileage."
        elif self.vehicle_id and self.mileage > self.vehicle.current_mileage:
            errors["mileage"] = (
                "Service mileage cannot exceed the vehicle's current mileage "
                f"({self.vehicle.current_mileage} km). Update the vehicle first."
            )

        if self.cost is None:
            errors["cost"] = "Completed services require the actual cost (0 is allowed)."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.service_type} for {self.vehicle} ({self.get_status_display()})"
