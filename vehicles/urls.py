from django.urls import path

from . import views


urlpatterns = [
    path("", views.vehicle_list, name="vehicle_list"),
    path("vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
]