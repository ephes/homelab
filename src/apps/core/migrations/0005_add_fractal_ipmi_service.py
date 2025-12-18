from django.db import migrations


def add_fractal_ipmi(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Fractal IPMI",
        defaults={
            "description": "IPMI/BMC management interface for the fractal server",
            "url": "https://asrock.fritz.box/",
            "icon": "fas fa-microchip",
            "is_active": True,
            "order": 14,
        },
    )


def remove_fractal_ipmi(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Fractal IPMI").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_add_postfixadmin_service"),
    ]

    operations = [
        migrations.RunPython(add_fractal_ipmi, remove_fractal_ipmi),
    ]
