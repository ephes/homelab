from django.db import migrations


def add_takahe(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Takahe",
        defaults={
            "description": "Fediverse server for python-podcast.de",
            "url": "https://fedi.python-podcast.de/",
            "icon": "fas fa-comment-dots",
            "is_active": True,
            "order": 18,
        },
    )


def remove_takahe(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Takahe").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_add_qbittorrent_service"),
    ]

    operations = [
        migrations.RunPython(add_takahe, remove_takahe),
    ]
