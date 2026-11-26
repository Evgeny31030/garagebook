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