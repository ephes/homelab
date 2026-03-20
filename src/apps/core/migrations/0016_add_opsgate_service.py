from django.db import migrations


def add_opsgate_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="OpsGate",
        defaults={
            "description": "Approval queue and audit surface for human-reviewed operator actions",
            "url": "https://opsgate.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-clipboard-check",
            "is_active": True,
            "order": 25,
        },
    )


def remove_opsgate_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="OpsGate").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_add_logyard_service"),
    ]

    operations = [
        migrations.RunPython(add_opsgate_service, remove_opsgate_service),
    ]
