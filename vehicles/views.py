from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import F, Sum
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CompleteMaintenanceForm, MaintenanceRecordForm, VehicleForm
from .models import MaintenanceRecord, Vehicle


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
    completed_form = MaintenanceRecordForm(vehicle=vehicle, mode=MaintenanceRecord.Status.COMPLETED)
    planned_form = MaintenanceRecordForm(vehicle=vehicle, mode=MaintenanceRecord.Status.PLANNED, prefix="plan")

    if request.method == "POST":
        kind = request.POST.get("kind", "completed")
        if kind == MaintenanceRecord.Status.COMPLETED:
            completed_form = MaintenanceRecordForm(
                request.POST, vehicle=vehicle, mode=MaintenanceRecord.Status.COMPLETED
            )
            active_form = completed_form
        elif kind == MaintenanceRecord.Status.PLANNED:
            planned_form = MaintenanceRecordForm(
                request.POST, vehicle=vehicle, mode=MaintenanceRecord.Status.PLANNED,
                prefix="plan",
            )
            active_form = planned_form
        else:
            return HttpResponseBadRequest("Unknown maintenance type.")

        if active_form.is_valid():
            record = active_form.save(commit=False)
            record.vehicle = vehicle
            record.status = kind
            record.save()
            return redirect("vehicle_detail", pk=vehicle.pk)

    completed_records = vehicle.maintenance_records.filter(
        status=MaintenanceRecord.Status.COMPLETED
    ).order_by("-date", "-id")
    planned_records = vehicle.maintenance_records.filter(
        status=MaintenanceRecord.Status.PLANNED
    ).order_by(F("date").asc(nulls_last=True), F("mileage").asc(nulls_last=True), "id")
    total_cost = completed_records.aggregate(total=Sum("cost"))["total"] or Decimal("0.00")

    return render(
        request,
        "vehicles/vehicle_detail.html",
        {
            "vehicle": vehicle,
            "maintenance_form": completed_form,  # Preserve compatibility with existing tests.
            "completed_form": completed_form,
            "planned_form": planned_form,
            "maintenance_records": completed_records,
            "planned_records": planned_records,
            "total_maintenance_cost": total_cost,
        },
    )


def maintenance_complete(request, pk, record_pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    record = get_object_or_404(
        MaintenanceRecord,
        pk=record_pk,
        vehicle=vehicle,
        status=MaintenanceRecord.Status.PLANNED,
    )

    if request.method == "POST":
        form = CompleteMaintenanceForm(request.POST, vehicle=vehicle)
        if form.is_valid():
            record.status = MaintenanceRecord.Status.COMPLETED
            record.date = form.cleaned_data["date"]
            record.mileage = form.cleaned_data["mileage"]
            record.cost = form.cleaned_data["cost"]
            try:
                record.full_clean()
            except ValidationError as exc:
                for field, messages in exc.message_dict.items():
                    form.add_error(field if field in form.fields else None, messages)
            else:
                record.save(update_fields=["status", "date", "mileage", "cost"])
                return redirect("vehicle_detail", pk=vehicle.pk)
    else:
        form = CompleteMaintenanceForm(
            vehicle=vehicle,
            initial={"date": timezone.localdate(), "mileage": vehicle.current_mileage},
        )

    return render(
        request,
        "vehicles/maintenance_complete.html",
        {"vehicle": vehicle, "record": record, "form": form},
    )


@require_http_methods(["GET", "POST"])
def maintenance_plan_edit(request, pk, record_pk):
    """Edit a plan belonging to this vehicle; never edit completed services here."""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    record = get_object_or_404(
        MaintenanceRecord,
        pk=record_pk,
        vehicle=vehicle,
        status=MaintenanceRecord.Status.PLANNED,
    )
    form = MaintenanceRecordForm(
        request.POST if request.method == "POST" else None,
        instance=record,
        vehicle=vehicle,
        mode=MaintenanceRecord.Status.PLANNED,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("vehicle_detail", pk=vehicle.pk)

    return render(
        request,
        "vehicles/maintenance_plan_edit.html",
        {"vehicle": vehicle, "record": record, "form": form},
    )


@require_http_methods(["GET", "POST"])
def maintenance_plan_delete(request, pk, record_pk):
    """Show confirmation on GET; permanently delete a plan only on POST."""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    record = get_object_or_404(
        MaintenanceRecord,
        pk=record_pk,
        vehicle=vehicle,
        status=MaintenanceRecord.Status.PLANNED,
    )
    if request.method == "POST":
        record.delete()
        return redirect("vehicle_detail", pk=vehicle.pk)
    return render(
        request,
        "vehicles/maintenance_plan_delete.html",
        {"vehicle": vehicle, "record": record},
    )
