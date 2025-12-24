from django.db import migrations


def add_mastodon(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Mastodon",
        defaults={
            "description": "Mastodon instance for wersdoerfer.de",
            "url": "https://fedi.wersdoerfer.de/",
            "icon": "fab fa-mastodon",
            "is_active": True,
            "order": 19,
        },
    )


def remove_mastodon(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Mastodon").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_add_takahe_service"),
    ]

    operations = [
        migrations.RunPython(add_mastodon, remove_mastodon),
    ]
