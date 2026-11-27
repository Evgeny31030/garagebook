from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .feature_forms import BuildModificationForm, ComponentScheduleForm
from .forms import MaintenanceRecordForm
from .models import BuildModification, ComponentSchedule, MaintenanceRecord, Vehicle


def car_health(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    schedules = {s.component: s for s in vehicle.component_schedules.select_related("vehicle")}
    components = []
    for code, label in ComponentSchedule.Component.choices:
        schedule = schedules.get(code)
        progress = schedule.progress() if schedule else {"state": "unknown", "label": "No data"}
        history = list(schedule.replacement_history()) if schedule else []
        count = len(history)
        frequency = "low" if count < 3 else "medium" if count <= 5 else "high"
        components.append({"code": code, "name": label, "schedule": schedule,
                           "history": history, "count": count, "frequency": frequency, **progress})
    return render(request, "vehicles/car_health.html", {"vehicle": vehicle, "components": components,
                  "component_map": {item["code"]: item for item in components}})


@require_http_methods(["GET", "POST"])
def component_edit(request, pk, component):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if component not in ComponentSchedule.Component.values:
        raise Http404
    schedule = vehicle.component_schedules.filter(component=component).first() or ComponentSchedule(vehicle=vehicle, component=component)
    form = ComponentScheduleForm(request.POST if request.method == "POST" else None, instance=schedule, vehicle=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("car_health", pk=pk)
    return render(request, "vehicles/feature_form.html", {"vehicle": vehicle, "form": form, "heading": f"Configure {schedule.get_component_display()}", "back_url": "car_health", "eyebrow": "CAR HEALTH"})


@require_http_methods(["GET", "POST"])
def component_replacement_create(request, pk, component):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if component not in ComponentSchedule.Component.values:
        raise Http404
    label = ComponentSchedule.Component(component).label
    form = MaintenanceRecordForm(request.POST if request.method == "POST" else None,
                                 vehicle=vehicle, initial={"service_type": f"{label} replacement"})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            record = form.save()
            schedule, _ = ComponentSchedule.objects.get_or_create(vehicle=vehicle, component=component)
            schedule.replacements.add(record)
        return redirect("car_health", pk=pk)
    return render(request, "vehicles/feature_form.html", {"vehicle": vehicle, "form": form,
                  "heading": f"Record {label} replacement", "back_url": "car_health", "eyebrow": "CAR HEALTH"})


def power_history(installed):
    """Chronological measured before/after values; never sum modification gains."""
    points = []
    latest_after = None
    for mod in installed.order_by("installed_on", "id"):
        for stage, hp in (("Before", mod.horsepower_before), ("After", mod.horsepower_after)):
            if hp is not None:
                points.append({"hp": hp, "name": mod.name, "date": mod.installed_on, "stage": stage})
                if stage == "After":
                    latest_after = points[-1]
    if not points:
        return {"points": [], "latest_after": None, "latest_measurement": None, "line": "", "ticks": []}
    low, high = min(p["hp"] for p in points), max(p["hp"] for p in points)
    padding = max(10, (high - low + 9) // 10)
    low, high = max(0, low - padding), high + padding
    for i, point in enumerate(points):
        point["x"] = 56 + round(548 * i / (len(points) - 1)) if len(points) > 1 else 330
        point["y"] = 16 + round(120 * (high - point["hp"]) / (high - low))
    ticks = [{"hp": high, "y": 16}, {"hp": (low + high) // 2, "y": 76}, {"hp": low, "y": 136}]
    return {"points": points, "latest_after": latest_after, "latest_measurement": points[-1],
            "line": " ".join(f"{p['x']},{p['y']}" for p in points), "ticks": ticks}


def build_tracker(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    installed = vehicle.build_modifications.filter(status=BuildModification.Status.INSTALLED).order_by("-installed_on", "-id")
    planned = vehicle.build_modifications.filter(status=BuildModification.Status.PLANNED)
    return render(request, "vehicles/build_tracker.html", {"vehicle": vehicle, "installed": installed, "planned": planned, "spent": installed.aggregate(total=Sum("cost"))["total"] or Decimal("0.00"), "estimated": planned.aggregate(total=Sum("cost"))["total"] or Decimal("0.00"), "unknown_estimates": planned.filter(cost__isnull=True).count(), "power": power_history(installed)})


@require_http_methods(["GET", "POST"])
def modification_edit(request, pk, mod_pk=None):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    modification = get_object_or_404(vehicle.build_modifications, pk=mod_pk) if mod_pk is not None else BuildModification(vehicle=vehicle)
    form = BuildModificationForm(request.POST if request.method == "POST" else None, instance=modification, vehicle=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("build_tracker", pk=pk)
    return render(request, "vehicles/feature_form.html", {"vehicle": vehicle, "form": form, "heading": "Edit modification" if mod_pk is not None else "Add modification", "back_url": "build_tracker", "eyebrow": "BUILD TRACKER"})


@require_http_methods(["GET", "POST"])
def modification_delete(request, pk, mod_pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    modification = get_object_or_404(vehicle.build_modifications, pk=mod_pk)
    if request.method == "POST":
        modification.delete()
        return redirect("build_tracker", pk=pk)
    return render(request, "vehicles/build_delete.html", {"vehicle": vehicle, "modification": modification})
