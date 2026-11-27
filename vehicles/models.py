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


class ComponentSchedule(models.Model):
    class Component(models.TextChoices):
        ENGINE = "engine", "Engine oil"
        TRANSMISSION = "transmission", "Transmission"
        BRAKES = "brakes", "Brakes"
        TIRES = "tires", "Tires"
        BATTERY = "battery", "Battery"
        COOLING = "cooling", "Cooling system"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="component_schedules")
    component = models.CharField(max_length=16, choices=Component.choices)
    replacements = models.ManyToManyField(MaintenanceRecord, blank=True, related_name="component_replacements")
    interval_km = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    interval_days = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["vehicle", "component"], name="unique_vehicle_component_schedule")]

    def replacement_history(self):
        if not self.pk:
            return MaintenanceRecord.objects.none()
        return self.replacements.filter(
            vehicle_id=self.vehicle_id, status=MaintenanceRecord.Status.COMPLETED
        ).order_by("-date", "-id")

    @property
    def last_service(self):
        return self.replacement_history().first()

    def progress(self, today=None):
        from datetime import timedelta
        today = today or timezone.localdate()
        record = self.last_service
        result = {"state": "unknown", "label": "No data", "km_left": None, "days_left": None, "due_date": None, "due_mileage": None}
        if not record or record.vehicle_id != self.vehicle_id or record.status != MaintenanceRecord.Status.COMPLETED:
            return result
        if self.interval_km and record.mileage is not None and record.mileage <= self.vehicle.current_mileage:
            result["due_mileage"] = record.mileage + self.interval_km
            result["km_left"] = result["due_mileage"] - self.vehicle.current_mileage
        if self.interval_days and record.date and record.date <= today:
            try:
                result["due_date"] = record.date + timedelta(days=self.interval_days)
                result["days_left"] = (result["due_date"] - today).days
            except OverflowError:
                pass
        k, d = result["km_left"], result["days_left"]
        if (k is not None and k <= 0) or (d is not None and d <= 0):
            result.update(state="due", label="Due / overdue")
        elif (k is not None and k <= 1000) or (d is not None and d <= 30):
            result.update(state="soon", label="Due soon")
        elif k is not None or d is not None:
            result.update(state="ok", label="On schedule")
        return result


class BuildModification(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        INSTALLED = "installed", "Installed"

    class Category(models.TextChoices):
        ENGINE = "engine", "Engine / ECU"
        EXHAUST = "exhaust", "Exhaust"
        SUSPENSION = "suspension", "Suspension"
        BRAKES = "brakes", "Brakes"
        WHEELS = "wheels", "Wheels / tires"
        BODY = "body", "Exterior / interior"
        OTHER = "other", "Other"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="build_modifications")
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.OTHER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    installed_on = models.DateField(null=True, blank=True)
    horsepower_before = models.PositiveIntegerField(null=True, blank=True)
    horsepower_after = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="build_cost_nonnegative"),
            models.CheckConstraint(condition=(models.Q(status="planned", installed_on__isnull=True) | models.Q(status="installed", installed_on__isnull=False, cost__isnull=False)), name="build_status_fields"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.INSTALLED:
            if self.installed_on is None:
                errors["installed_on"] = "Enter the actual installation date."
            elif self.installed_on > timezone.localdate():
                errors["installed_on"] = "Installation date cannot be in the future."
            if self.cost is None:
                errors["cost"] = "Enter the actual cost (0 is allowed)."
        elif self.status == self.Status.PLANNED:
            if self.installed_on is not None:
                errors["installed_on"] = "Leave the installation date blank for a plan."
            if self.horsepower_before is not None or self.horsepower_after is not None:
                errors["horsepower_after"] = "Enter measured power only after installation."
        if errors:
            raise ValidationError(errors)

    @property
    def horsepower_change(self):
        if self.horsepower_before is not None and self.horsepower_after is not None:
            return self.horsepower_after - self.horsepower_before
        return None
