from django.shortcuts import get_object_or_404, redirect, render

from .forms import VehicleForm
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
    return render(request, "vehicles/vehicle_detail.html", {"vehicle": vehicle})