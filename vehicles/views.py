from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MaintenanceRecordForm, VehicleForm
from .models import Vehicle


def vehicle_list(request):
    vehicles = Vehicle.objects.order_by("-id")
    return render(request, "vehicles/vehicle_list.html", {"vehicles": vehicles})


def vehicle_create(request):
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            return redirect("vehicle_detail", pk=vehicle.pk)
    else:
        form = VehicleForm()

    return render(
        request,
        "vehicles/vehicle_form.html",
        {"form": form, "is_edit": False},
    )


def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            return redirect("vehicle_detail", pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle)

    return render(
        request,
        "vehicles/vehicle_form.html",
        {"form": form, "is_edit": True, "vehicle": vehicle},
    )


def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        maintenance_form = MaintenanceRecordForm(request.POST)
        if maintenance_form.is_valid():
            record = maintenance_form.save(commit=False)
            record.vehicle = vehicle
            record.save()
            return redirect("vehicle_detail", pk=vehicle.pk)
    else:
        maintenance_form = MaintenanceRecordForm()

    records = vehicle.maintenance_records.all()
    total_cost = records.aggregate(total=Sum("cost"))["total"] or Decimal("0.00")
    return render(
        request,
        "vehicles/vehicle_detail.html",
        {
            "vehicle": vehicle,
            "maintenance_form": maintenance_form,
            "maintenance_records": records,
            "total_maintenance_cost": total_cost,
        },
    )
