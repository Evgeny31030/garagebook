from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BuildModification, ComponentSchedule, MaintenanceRecord, Vehicle


class GarageFeatureTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.vehicle = Vehicle.objects.create(make="Audi", model="RS7", year=2023, current_mileage=52000)
        self.other = Vehicle.objects.create(make="BMW", model="M3", year=2023, current_mileage=52000)
        self.service = MaintenanceRecord.objects.create(vehicle=self.vehicle, service_type="Oil change", date=self.today - timedelta(days=20), mileage=50000, cost=100)

    def test_vehicle_links_and_unknown_health(self):
        self.assertContains(self.client.get(reverse("vehicle_detail", args=[self.vehicle.pk])), "Car Health")
        response = self.client.get(reverse("car_health", args=[self.vehicle.pk]))
        self.assertContains(response, "No data")

    def test_configure_schedule_and_calculate_remaining(self):
        url = reverse("component_edit", args=[self.vehicle.pk, "engine"])
        response = self.client.post(url, {"replacements": self.service.pk, "interval_km": 3000, "interval_days": 90})
        self.assertRedirects(response, reverse("car_health", args=[self.vehicle.pk]))
        schedule = self.vehicle.component_schedules.get()
        self.assertEqual(schedule.progress(self.today)["state"], "soon")
        self.assertEqual(schedule.progress(self.today)["km_left"], 1000)
        self.assertEqual(schedule.progress(self.today)["days_left"], 70)
        self.assertContains(self.client.get(reverse("car_health", args=[self.vehicle.pk])), "53000 km")

    def test_earliest_limit_wins(self):
        schedule = ComponentSchedule.objects.create(vehicle=self.vehicle, component="engine", interval_km=10000, interval_days=20)
        schedule.replacements.add(self.service)
        self.assertEqual(schedule.progress(self.today)["state"], "due")
        schedule.interval_days = 100
        self.assertEqual(schedule.progress(self.today)["state"], "ok")

    def test_other_vehicle_or_planned_service_cannot_be_linked(self):
        other = MaintenanceRecord.objects.create(vehicle=self.other, service_type="Other", date=self.today, mileage=51000, cost=100)
        planned = MaintenanceRecord.objects.create(vehicle=self.vehicle, service_type="Future", status="planned")
        url = reverse("component_edit", args=[self.vehicle.pk, "engine"])
        for record in [other, planned]:
            response = self.client.post(url, {"replacements": record.pk, "interval_km": 5000})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(self.vehicle.component_schedules.exists())

    def test_zero_interval_rejected(self):
        response = self.client.post(reverse("component_edit", args=[self.vehicle.pk, "engine"]), {"replacements": self.service.pk, "interval_km": 0})
        self.assertIn("interval_km", response.context["form"].errors)

    def test_replacement_history_counts_and_colors(self):
        schedule = ComponentSchedule.objects.create(vehicle=self.vehicle, component="engine", interval_km=10000)
        records = [self.service] + [MaintenanceRecord.objects.create(vehicle=self.vehicle, service_type=f"Oil replacement {i}", date=self.today - timedelta(days=i), mileage=51000, cost=20) for i in range(1, 6)]
        url = reverse("car_health", args=[self.vehicle.pk])
        for count, color in [(0, "low"), (2, "low"), (3, "medium"), (5, "medium"), (6, "high")]:
            schedule.replacements.set(records[:count])
            response = self.client.get(url)
            item = response.context["component_map"]["engine"]
            self.assertEqual(item["count"], count)
            self.assertEqual(item["frequency"], color)
            self.assertContains(response, f"car-part replacement-{color}")
        self.assertEqual(schedule.last_service, records[1])
        self.assertEqual(schedule.progress(self.today)["km_left"], 9000)

    def test_configure_multiple_replacements_and_unlink_without_deletion(self):
        second = MaintenanceRecord.objects.create(vehicle=self.vehicle, service_type="Oil replacement", date=self.today, mileage=52000, cost=50)
        url = reverse("component_edit", args=[self.vehicle.pk, "engine"])
        self.assertRedirects(self.client.post(url, {"replacements": [self.service.pk, second.pk], "interval_km": 10000}), reverse("car_health", args=[self.vehicle.pk]))
        schedule = self.vehicle.component_schedules.get()
        self.assertEqual(schedule.replacement_history().count(), 2)
        self.assertEqual(schedule.last_service, second)
        self.client.post(url, {"replacements": [self.service.pk], "interval_km": 10000})
        self.assertEqual(schedule.replacement_history().count(), 1)
        self.assertTrue(MaintenanceRecord.objects.filter(pk=second.pk).exists())

    def test_record_replacement_creates_completed_service_once(self):
        url = reverse("component_replacement_create", args=[self.vehicle.pk, "brakes"])
        data = {"service_type": "Brake pad replacement", "date": self.today.isoformat(), "mileage": 52000, "cost": "80"}
        self.assertRedirects(self.client.post(url, data), reverse("car_health", args=[self.vehicle.pk]))
        schedule = self.vehicle.component_schedules.get(component="brakes")
        self.assertEqual(schedule.replacement_history().count(), 1)
        self.assertEqual(schedule.last_service.status, MaintenanceRecord.Status.COMPLETED)
        self.assertEqual(self.client.get(reverse("vehicle_detail", args=[self.vehicle.pk])).context["total_maintenance_cost"], Decimal("180"))
        response = self.client.post(url, {**data, "mileage": 53000})
        self.assertIn("mileage", response.context["form"].errors)
        self.assertEqual(schedule.replacement_history().count(), 1)
        self.assertEqual(self.client.get(reverse("component_replacement_create", args=[self.vehicle.pk, "invalid"])).status_code, 404)

    def test_power_history_order_latest_and_plans_excluded(self):
        BuildModification.objects.create(vehicle=self.vehicle, name="Later tune", status="installed", installed_on=self.today, cost=10, horsepower_before=650, horsepower_after=620)
        BuildModification.objects.create(vehicle=self.vehicle, name="Earlier tune", status="installed", installed_on=self.today-timedelta(days=1), cost=10, horsepower_before=600, horsepower_after=650)
        BuildModification.objects.create(vehicle=self.vehicle, name="Planned", horsepower_after=900)
        BuildModification.objects.create(vehicle=self.other, name="Other", status="installed", installed_on=self.today, cost=10, horsepower_after=1000)
        response = self.client.get(reverse("build_tracker", args=[self.vehicle.pk]))
        power = response.context["power"]
        self.assertEqual([p["hp"] for p in power["points"]], [600, 650, 650, 620])
        self.assertEqual(power["latest_after"]["hp"], 620)
        self.assertContains(response, "620 hp")
        self.assertContains(response, "power-line")

    def test_power_empty_single_measurement_and_missing_after(self):
        url = reverse("build_tracker", args=[self.vehicle.pk])
        self.assertContains(self.client.get(url), "Not measured")
        BuildModification.objects.create(vehicle=self.vehicle, name="Baseline", status="installed", installed_on=self.today, cost=0, horsepower_before=500)
        response = self.client.get(url)
        self.assertEqual(len(response.context["power"]["points"]), 1)
        self.assertIsNone(response.context["power"]["latest_after"])
        self.assertEqual(response.context["power"]["latest_measurement"]["hp"], 500)
        self.assertContains(response, "500 hp")

    def build_data(self, **kwargs):
        return {"name": "ECU tune", "category": "engine", "status": "planned", "cost": "150", **kwargs}

    def test_build_create_edit_and_separate_totals(self):
        self.assertRedirects(self.client.post(reverse("modification_create", args=[self.vehicle.pk]), self.build_data()), reverse("build_tracker", args=[self.vehicle.pk]))
        mod = self.vehicle.build_modifications.get()
        response = self.client.get(reverse("build_tracker", args=[self.vehicle.pk]))
        self.assertEqual(response.context["spent"], Decimal("0.00"))
        self.assertEqual(response.context["estimated"], Decimal("150.00"))
        self.assertRedirects(self.client.post(reverse("modification_edit", args=[self.vehicle.pk, mod.pk]), self.build_data(status="installed", installed_on=self.today.isoformat(), cost="170", horsepower_before=600, horsepower_after=650)), reverse("build_tracker", args=[self.vehicle.pk]))
        mod.refresh_from_db()
        self.assertEqual(mod.horsepower_change, 50)
        response = self.client.get(reverse("build_tracker", args=[self.vehicle.pk]))
        self.assertEqual(response.context["spent"], Decimal("170.00"))
        self.assertEqual(response.context["estimated"], Decimal("0.00"))
        self.assertEqual(self.client.get(reverse("vehicle_detail", args=[self.vehicle.pk])).context["total_maintenance_cost"], Decimal("100"))

    def test_invalid_build_data(self):
        url = reverse("modification_create", args=[self.vehicle.pk])
        for data, field in [(self.build_data(cost="-1"), "cost"), (self.build_data(status="installed", installed_on=(self.today + timedelta(days=1)).isoformat()), "installed_on"), (self.build_data(status="installed", cost="", installed_on=self.today.isoformat()), "cost"), (self.build_data(horsepower_after=700), "horsepower_after")]:
            response = self.client.post(url, data)
            self.assertIn(field, response.context["form"].errors)
        self.assertFalse(self.vehicle.build_modifications.exists())

    def test_build_free_install_and_unknown_estimate(self):
        url = reverse("modification_create", args=[self.vehicle.pk])
        self.client.post(url, self.build_data(cost=""))
        self.client.post(url, self.build_data(status="installed", cost="0", installed_on=self.today.isoformat()))
        response = self.client.get(reverse("build_tracker", args=[self.vehicle.pk]))
        self.assertEqual(response.context["unknown_estimates"], 1)
        self.assertEqual(response.context["installed"].count(), 1)

    def test_delete_requires_post_and_vehicle_match(self):
        mod = BuildModification.objects.create(vehicle=self.vehicle, name="Exhaust")
        url = reverse("modification_delete", args=[self.vehicle.pk, mod.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(BuildModification.objects.filter(pk=mod.pk).exists())
        for route in ["modification_edit", "modification_delete"]:
            self.assertEqual(self.client.post(reverse(route, args=[self.other.pk, mod.pk])).status_code, 404)
        self.assertRedirects(self.client.post(url), reverse("build_tracker", args=[self.vehicle.pk]))
        self.assertFalse(BuildModification.objects.filter(pk=mod.pk).exists())
