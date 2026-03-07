from django.db import migrations


def add_graphyard_and_grafana(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Graphyard",
        defaults={
            "description": "Metrics catalog and operator interface for the homelab metrics platform",
            "url": "https://graphyard.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-project-diagram",
            "is_active": True,
            "order": 23,
        },
    )
    Service.objects.update_or_create(
        name="Grafana",
        defaults={
            "description": "Time-series dashboards and drill-down views for Graphyard metrics",
            "url": "https://grafana.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-chart-area",
            "is_active": True,
            "order": 24,
        },
    )


def remove_graphyard_and_grafana(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name__in=["Graphyard", "Grafana"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_add_openclaw_service"),
    ]

    operations = [
        migrations.RunPython(add_graphyard_and_grafana, remove_graphyard_and_grafana),
    ]
