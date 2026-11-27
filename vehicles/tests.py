from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import MaintenanceRecordForm
from .models import MaintenanceRecord, Vehicle


class VehicleMaintenanceTests(TestCase):
    def setUp(self):
        self.first = Vehicle.objects.create(
            make="Toyota", model="Camry", year=2018, current_mileage=82000
        )
        self.second = Vehicle.objects.create(
            make="Honda", model="Civic", year=2019, current_mileage=44000
        )
        self.first_url = reverse("vehicle_detail", args=[self.first.pk])
        self.second_url = reverse("vehicle_detail", args=[self.second.pk])
        self.valid_data = {
            "date": "2026-11-25",
            "service_type": "Oil change",
            "mileage": "82000",
            "cost": "150.25",
            "notes": "",
        }

    def test_create_record_and_persist_on_vehicle_page(self):
        response = self.client.post(self.first_url, self.valid_data)
        self.assertRedirects(response, self.first_url)
        record = MaintenanceRecord.objects.get()
        self.assertEqual(record.vehicle_id, self.first.pk)
        self.assertEqual(record.cost, Decimal("150.25"))
        self.assertEqual(record.notes, "")
        response = self.client.get(self.first_url)
        self.assertContains(response, "Oil change")
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("150.25"))
        self.assertContains(response, "$150.25")
        self.assertContains(response, "Cost (USD)")

    def test_history_order_is_newest_first(self):
        MaintenanceRecord.objects.create(
            vehicle=self.first, date=date(2026, 1, 1),
            service_type="Earlier", mileage=100, cost=Decimal("50.00"),
        )
        MaintenanceRecord.objects.create(
            vehicle=self.first, date=date(2026, 2, 1),
            service_type="Later", mileage=200, cost=Decimal("20.00"),
        )
        response = self.client.get(self.first_url)
        self.assertQuerySetEqual(
            response.context["maintenance_records"],
            ["Later", "Earlier"],
            transform=lambda record: record.service_type,
        )
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("70.00"))

    def test_records_do_not_leak_to_other_vehicle(self):
        self.client.post(self.first_url, self.valid_data)
        response = self.client.get(self.second_url)
        self.assertNotContains(response, "Oil change")
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("0.00"))
        self.assertEqual(MaintenanceRecord.objects.filter(vehicle=self.second).count(), 0)

    def test_required_fields_are_enforced(self):
        for field in ("date", "service_type", "mileage", "cost"):
            with self.subTest(field=field):
                data = {**self.valid_data, field: ""}
                response = self.client.post(self.first_url, data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["maintenance_form"].errors)
        self.assertEqual(MaintenanceRecord.objects.count(), 0)

    def test_negative_mileage_or_cost_are_rejected(self):
        for field in ("mileage", "cost"):
            with self.subTest(field=field):
                data = {**self.valid_data, field: "-1"}
                response = self.client.post(self.first_url, data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["maintenance_form"].errors)
        self.assertEqual(MaintenanceRecord.objects.count(), 0)

    def test_vehicle_is_not_editable_in_maintenance_form(self):
        self.assertNotIn("vehicle", MaintenanceRecordForm().fields)
        self.client.post(self.first_url, {**self.valid_data, "vehicle": self.second.pk})
        self.assertEqual(MaintenanceRecord.objects.get().vehicle, self.first)

    def test_record_is_removed_when_vehicle_is_removed(self):
        self.client.post(self.first_url, self.valid_data)
        self.first.delete()
        self.assertFalse(MaintenanceRecord.objects.exists())
