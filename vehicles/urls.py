from django.urls import path

from . import views


urlpatterns = [
    path("", views.vehicle_list, name="vehicle_list"),
    path("vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path(
        "vehicles/<int:pk>/maintenance/<int:record_pk>/complete/",
        views.maintenance_complete,
        name="maintenance_complete",
    ),
    path(
        "vehicles/<int:pk>/maintenance/<int:record_pk>/edit/",
        views.maintenance_plan_edit,
        name="maintenance_plan_edit",
    ),
    path(
        "vehicles/<int:pk>/maintenance/<int:record_pk>/delete/",
        views.maintenance_plan_delete,
        name="maintenance_plan_delete",
    ),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
]
