from django.db import migrations


def add_logyard_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Logyard",
        defaults={
            "description": "Central homelab logs in the shared Grafana Explore and Logyard dashboard flow",
            "url": "https://grafana.home.xn--wersdrfer-47a.de/d/logyard-home/logyard-overview",
            "icon": "fas fa-file-lines",
            "is_active": True,
            "order": 25,
        },
    )


def remove_logyard_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Logyard").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_add_graphyard_and_grafana_services"),
    ]

    operations = [
        migrations.RunPython(add_logyard_service, remove_logyard_service),
    ]
