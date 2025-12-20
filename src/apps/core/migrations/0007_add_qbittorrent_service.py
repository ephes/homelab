from django.db import migrations


def add_qbittorrent(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="qBittorrent",
        defaults={
            "description": "BitTorrent client for downloads and seeding",
            "url": "https://torrent.wersdörfer.de",
            "icon": "fas fa-magnet",
            "is_active": True,
            "order": 17,
        },
    )


def remove_qbittorrent(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="qBittorrent").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_add_cms_services"),
    ]

    operations = [
        migrations.RunPython(add_qbittorrent, remove_qbittorrent),
    ]
