from django.db import migrations


def add_takahe(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.using(schema_editor.connection.alias).get_or_create(
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
    """Retain rows: these historical seeds did not record creation ownership."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_add_qbittorrent_service"),
    ]

    operations = [
        migrations.RunPython(add_takahe, remove_takahe),
    ]
