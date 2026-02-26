from django.db import migrations


def add_openclaw(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="OpenClaw",
        defaults={
            "description": "AI automation gateway and web dashboard",
            "url": "https://openclaw.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-robot",
            "is_active": True,
            "order": 22,
        },
    )


def remove_openclaw(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="OpenClaw").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_update_open_webui_service"),
    ]

    operations = [
        migrations.RunPython(add_openclaw, remove_openclaw),
    ]
