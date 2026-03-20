from django.db import migrations


def add_archive_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Archive",
        defaults={
            "description": (
                "Self-hosted archive for saved links, podcast episodes, "
                "and videos with summaries and public feeds"
            ),
            "url": "https://archive.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-box-archive",
            "is_active": True,
            "order": 26,
        },
    )


def remove_archive_service(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Archive").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_add_logyard_service"),
    ]

    operations = [
        migrations.RunPython(add_archive_service, remove_archive_service),
    ]
