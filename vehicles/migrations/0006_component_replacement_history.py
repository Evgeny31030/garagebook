from django.db import migrations, models


def forward(apps, schema_editor):
    Schedule = apps.get_model("vehicles", "ComponentSchedule")
    db = schema_editor.connection.alias
    for schedule in Schedule.objects.using(db).exclude(last_service_id=None).iterator():
        if (schedule.last_service.vehicle_id == schedule.vehicle_id
                and schedule.last_service.status == "completed"):
            schedule.replacements.add(schedule.last_service_id)


def backward(apps, schema_editor):
    Schedule = apps.get_model("vehicles", "ComponentSchedule")
    db = schema_editor.connection.alias
    for schedule in Schedule.objects.using(db).iterator():
        latest = schedule.replacements.filter(vehicle_id=schedule.vehicle_id, status="completed").order_by("-date", "-id").first()
        schedule.last_service_id = latest.pk if latest else None
        schedule.save(using=db, update_fields=["last_service"])


class Migration(migrations.Migration):
    dependencies = [("vehicles", "0005_car_health_build_tracker")]
    operations = [
        migrations.AddField(model_name="componentschedule", name="replacements", field=models.ManyToManyField(blank=True, related_name="component_replacements", to="vehicles.maintenancerecord")),
        migrations.RunPython(forward, backward),
        migrations.RemoveField(model_name="componentschedule", name="last_service"),
    ]
