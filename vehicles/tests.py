from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
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


class PlannedMaintenanceTests(TestCase):
    def setUp(self):
        self.car = Vehicle.objects.create(
            make="Audi", model="RS7", year=2023, current_mileage=52000
        )
        self.other = Vehicle.objects.create(
            make="BMW", model="330i", year=2020, current_mileage=40000
        )
        self.url = reverse("vehicle_detail", args=[self.car.pk])
        self.other_url = reverse("vehicle_detail", args=[self.other.pk])

    def plan(self, **values):
        return self.client.post(
            self.url,
            {
                "kind": "planned",
                "plan-service_type": "Transmission oil",
                "plan-date": "",
                "plan-mileage": "",
                "plan-cost": "",
                "plan-notes": "",
                **values,
            },
        )

    def create_completed(self, **values):
        return self.client.post(
            self.url,
            {
                "kind": "completed",
                "date": "2026-11-20",
                "service_type": "Oil change",
                "mileage": "51000",
                "cost": "250.00",
                "notes": "",
                **values,
            },
        )

    def test_planned_service_without_unknown_details(self):
        response = self.plan()
        self.assertRedirects(response, self.url)
        record = MaintenanceRecord.objects.get()
        self.assertEqual(record.status, MaintenanceRecord.Status.PLANNED)
        self.assertIsNone(record.date)
        self.assertIsNone(record.mileage)
        self.assertIsNone(record.cost)
        response = self.client.get(self.url)
        self.assertContains(response, "Transmission oil")
        self.assertContains(response, "Mileage not set")
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("0.00"))

    def test_future_plan_with_target_mileage_above_current_is_allowed(self):
        from django.utils import timezone
        from datetime import timedelta

        later = timezone.localdate() + timedelta(days=90)
        response = self.plan(
            **{
                "plan-date": later.isoformat(),
                "plan-mileage": "100000",
                "plan-cost": "900.00",
            }
        )
        self.assertRedirects(response, self.url)
        record = MaintenanceRecord.objects.get()
        self.assertEqual(record.date, later)
        self.assertEqual(record.mileage, 100000)
        self.assertEqual(record.cost, Decimal("900.00"))
        self.assertEqual(
            self.client.get(self.url).context["total_maintenance_cost"],
            Decimal("0.00"),
        )
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 52000)

    def test_planned_service_rejects_past_target_date(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        response = self.plan(**{"plan-date": yesterday.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["planned_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_planned_service_rejects_target_mileage_below_current(self):
        response = self.plan(**{"plan-mileage": "51999"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("mileage", response.context["planned_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_completed_mileage_above_current_has_one_specific_error(self):
        response = self.create_completed(mileage="54000")
        self.assertEqual(response.status_code, 200)
        errors = response.context["completed_form"].errors["mileage"]
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot exceed", errors[0])
        self.assertNotIn("require", errors[0])
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_future_completed_date_has_one_specific_error(self):
        future = timezone.localdate() + timedelta(days=1)
        response = self.create_completed(date=future.isoformat())
        self.assertEqual(response.status_code, 200)
        errors = response.context["completed_form"].errors["date"]
        self.assertEqual(len(errors), 1)
        self.assertIn("future", errors[0])
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_planned_mileage_below_current_has_one_specific_error(self):
        response = self.plan(**{"plan-mileage": "50000"})
        self.assertEqual(response.status_code, 200)
        errors = response.context["planned_form"].errors["mileage"]
        self.assertEqual(len(errors), 1)
        self.assertIn("below", errors[0])
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_planned_service_accepts_today_and_current_mileage(self):
        response = self.plan(
            **{
                "plan-date": timezone.localdate().isoformat(),
                "plan-mileage": "52000",
                "plan-cost": "0",
            }
        )
        self.assertRedirects(response, self.url)
        record = MaintenanceRecord.objects.get()
        self.assertEqual(record.date, timezone.localdate())
        self.assertEqual(record.mileage, 52000)
        self.assertEqual(record.cost, Decimal("0.00"))

    def test_planned_form_has_input_bounds(self):
        response = self.client.get(self.url)
        planned_form = response.context["planned_form"]
        completed_form = response.context["completed_form"]
        self.assertEqual(
            planned_form.fields["date"].widget.attrs["min"],
            timezone.localdate().isoformat(),
        )
        self.assertEqual(planned_form.fields["mileage"].widget.attrs["min"], 52000)
        self.assertEqual(
            completed_form.fields["date"].widget.attrs["max"],
            timezone.localdate().isoformat(),
        )
        self.assertEqual(completed_form.fields["mileage"].widget.attrs["max"], 52000)

    def test_model_validation_blocks_invalid_planned_targets(self):
        planned = MaintenanceRecord(
            vehicle=self.car,
            status=MaintenanceRecord.Status.PLANNED,
            service_type="Inspection",
            date=timezone.localdate() - timedelta(days=1),
            mileage=52000,
        )
        with self.assertRaises(ValidationError) as caught:
            planned.full_clean()
        self.assertIn("date", caught.exception.message_dict)

        planned.date = timezone.localdate()
        planned.mileage = 51999
        with self.assertRaises(ValidationError) as caught:
            planned.full_clean()
        self.assertIn("mileage", caught.exception.message_dict)

    def test_completed_service_rejects_future_date(self):
        from django.utils import timezone
        from datetime import timedelta

        later = timezone.localdate() + timedelta(days=1)
        response = self.create_completed(date=later.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["completed_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_completed_service_rejects_mileage_above_current(self):
        response = self.create_completed(mileage="52001")
        self.assertEqual(response.status_code, 200)
        self.assertIn("mileage", response.context["completed_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 52000)

    def test_historical_service_before_ownership_is_allowed(self):
        response = self.create_completed(
            date="2024-01-01", mileage="22000", cost="0"
        )
        self.assertRedirects(response, self.url)
        record = MaintenanceRecord.objects.get()
        self.assertEqual(record.status, MaintenanceRecord.Status.COMPLETED)
        self.assertEqual(record.cost, Decimal("0.00"))

    def test_plan_only_requires_service_name(self):
        response = self.plan(**{"plan-service_type": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("service_type", response.context["planned_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_negative_plan_values_are_rejected(self):
        for field in ("mileage", "cost"):
            with self.subTest(field=field):
                response = self.plan(**{f"plan-{field}": "-1"})
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["planned_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_mark_planned_service_completed_uses_actual_values(self):
        self.plan(**{"plan-cost": "120.00", "plan-mileage": "60000"})
        record = MaintenanceRecord.objects.get()
        completion_url = reverse(
            "maintenance_complete", args=[self.car.pk, record.pk]
        )
        response = self.client.get(completion_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actual cost (USD)")

        response = self.client.post(
            completion_url,
            {"date": "2026-11-26", "mileage": "51500", "cost": "135.50"},
        )
        self.assertRedirects(response, self.url)
        record.refresh_from_db()
        self.assertEqual(record.status, MaintenanceRecord.Status.COMPLETED)
        self.assertEqual(record.mileage, 51500)
        self.assertEqual(record.cost, Decimal("135.50"))
        vehicle_response = self.client.get(self.url)
        self.assertQuerySetEqual(vehicle_response.context["planned_records"], [])
        self.assertEqual(
            vehicle_response.context["total_maintenance_cost"], Decimal("135.50")
        )
        self.assertEqual(self.client.get(completion_url).status_code, 404)
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_mileage, 52000)

    def test_completion_rejects_future_and_high_mileage(self):
        from django.utils import timezone
        from datetime import timedelta

        self.plan()
        record = MaintenanceRecord.objects.get()
        url = reverse("maintenance_complete", args=[self.car.pk, record.pk])
        for values, field in (
            ({"date": (timezone.localdate() + timedelta(days=1)).isoformat(), "mileage": "52000", "cost": "0"}, "date"),
            ({"date": "2026-11-20", "mileage": "999999", "cost": "0"}, "mileage"),
        ):
            with self.subTest(field=field):
                response = self.client.post(url, values)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                record.refresh_from_db()
                self.assertEqual(record.status, MaintenanceRecord.Status.PLANNED)
                self.assertEqual(record.cost, None)

    def test_planned_and_completed_are_isolated_between_vehicles(self):
        self.plan()
        self.create_completed()
        response = self.client.get(self.other_url)
        self.assertNotContains(response, "Transmission oil")
        self.assertNotContains(response, "Oil change")
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("0.00"))
        record = MaintenanceRecord.objects.get(status=MaintenanceRecord.Status.PLANNED)
        wrong_vehicle_url = reverse(
            "maintenance_complete", args=[self.other.pk, record.pk]
        )
        self.assertEqual(self.client.get(wrong_vehicle_url).status_code, 404)
        self.assertEqual(
            self.client.post(
                wrong_vehicle_url,
                {"date": "2026-11-20", "mileage": "1000", "cost": "1"},
            ).status_code,
            404,
        )

    def test_actual_and_planned_costs_do_not_mix(self):
        self.create_completed()
        self.plan(**{"plan-cost": "5000"})
        response = self.client.get(self.url)
        self.assertEqual(response.context["total_maintenance_cost"], Decimal("250.00"))
        self.assertEqual(response.context["planned_records"].count(), 1)
        self.assertEqual(response.context["maintenance_records"].count(), 1)

    def test_crafted_post_cannot_force_plan_status_without_plan_fields(self):
        response = self.client.post(
            self.url,
            {
                "kind": "completed", "status": "planned",
                "service_type": "Inspection", "date": "", "mileage": "", "cost": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["completed_form"].errors)
        self.assertFalse(MaintenanceRecord.objects.exists())

    def test_invalid_kind_is_rejected(self):
        response = self.client.post(self.url, {"kind": "unknown"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MaintenanceRecord.objects.exists())


class PlannedMaintenanceEditingTests(TestCase):
    def setUp(self):
        self.car = Vehicle.objects.create(
            make="Audi", model="RS7", year=2023, current_mileage=52000
        )
        self.other = Vehicle.objects.create(
            make="BMW", model="330i", year=2020, current_mileage=47000
        )
        self.record = MaintenanceRecord.objects.create(
            vehicle=self.car,
            status=MaintenanceRecord.Status.PLANNED,
            service_type="Oil change",
            mileage=60000,
            cost=Decimal("150.00"),
            notes="Engine oil",
        )
        self.edit_url = reverse("maintenance_plan_edit", args=[self.car.pk, self.record.pk])
        self.delete_url = reverse("maintenance_plan_delete", args=[self.car.pk, self.record.pk])
        self.detail_url = reverse("vehicle_detail", args=[self.car.pk])

    def valid_edit_data(self, **updates):
        return {
            "service_type": "Gearbox service",
            "date": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "mileage": "64000",
            "cost": "0",
            "notes": "Changed plan",
            **updates,
        }

    def test_plan_has_edit_and_delete_actions(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, self.edit_url)
        self.assertContains(response, self.delete_url)
        self.assertContains(response, "Mark as completed")

    def test_edit_plan_prefills_existing_values_and_updates_record(self):
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["service_type"], "Oil change")
        response = self.client.post(self.edit_url, self.valid_edit_data())
        self.assertRedirects(response, self.detail_url)
        self.record.refresh_from_db()
        self.assertEqual(self.record.service_type, "Gearbox service")
        self.assertEqual(self.record.mileage, 64000)
        self.assertEqual(self.record.cost, Decimal("0.00"))
        self.assertEqual(self.record.notes, "Changed plan")
        self.assertEqual(self.record.status, MaintenanceRecord.Status.PLANNED)
        self.assertEqual(self.record.vehicle_id, self.car.pk)
        self.assertEqual(
            self.client.get(self.detail_url).context["total_maintenance_cost"],
            Decimal("0.00"),
        )

    def test_edit_plan_allows_empty_optional_fields(self):
        response = self.client.post(self.edit_url, self.valid_edit_data(
            date="", mileage="", cost="", notes=""
        ))
        self.assertRedirects(response, self.detail_url)
        self.record.refresh_from_db()
        self.assertIsNone(self.record.date)
        self.assertIsNone(self.record.mileage)
        self.assertIsNone(self.record.cost)
        self.assertEqual(self.record.notes, "")

    def test_edit_plan_rejects_invalid_dates_mileage_and_required_name(self):
        for value, field in (
            ({"date": (timezone.localdate() - timedelta(days=1)).isoformat()}, "date"),
            ({"mileage": "51000"}, "mileage"),
            ({"cost": "-10"}, "cost"),
            ({"service_type": ""}, "service_type"),
        ):
            with self.subTest(field=field):
                response = self.client.post(self.edit_url, self.valid_edit_data(**value))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.record.refresh_from_db()
                self.assertEqual(self.record.service_type, "Oil change")
                self.assertEqual(self.record.mileage, 60000)

    def test_edit_post_cannot_move_plan_to_another_vehicle_or_complete_it(self):
        data = self.valid_edit_data(vehicle=str(self.other.pk), status="completed")
        self.assertRedirects(self.client.post(self.edit_url, data), self.detail_url)
        self.record.refresh_from_db()
        self.assertEqual(self.record.vehicle_id, self.car.pk)
        self.assertEqual(self.record.status, MaintenanceRecord.Status.PLANNED)

    def test_delete_is_confirmed_before_post_and_removes_only_plan(self):
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Are you sure")
        self.assertTrue(MaintenanceRecord.objects.filter(pk=self.record.pk).exists())
        self.assertEqual(self.client.put(self.delete_url).status_code, 405)
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, self.detail_url)
        self.assertFalse(MaintenanceRecord.objects.filter(pk=self.record.pk).exists())

    def test_edit_delete_cannot_access_other_vehicles_plan(self):
        wrong_edit = reverse("maintenance_plan_edit", args=[self.other.pk, self.record.pk])
        wrong_delete = reverse("maintenance_plan_delete", args=[self.other.pk, self.record.pk])
        for url in (wrong_edit, wrong_delete):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.valid_edit_data()).status_code, 404)
        self.assertTrue(MaintenanceRecord.objects.filter(pk=self.record.pk).exists())

    def test_completed_service_cannot_be_edited_or_deleted_as_a_plan(self):
        completed = MaintenanceRecord.objects.create(
            vehicle=self.car,
            status=MaintenanceRecord.Status.COMPLETED,
            service_type="Old repair",
            date=timezone.localdate(),
            mileage=50000,
            cost=Decimal("500.00"),
        )
        response = self.client.get(self.detail_url)
        self.assertNotContains(
            response,
            reverse("maintenance_plan_edit", args=[self.car.pk, completed.pk]),
        )
        for name in ("maintenance_plan_edit", "maintenance_plan_delete"):
            url = reverse(name, args=[self.car.pk, completed.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.valid_edit_data()).status_code, 404)
        self.assertTrue(MaintenanceRecord.objects.filter(pk=completed.pk).exists())
