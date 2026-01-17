from django.db import migrations


def add_open_webui(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="Open WebUI",
        defaults={
            "description": "Chat interface for local LLMs (Open WebUI)",
            "url": "https://chat.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-comments",
            "is_active": True,
            "order": 20,
        },
    )


def remove_open_webui(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Open WebUI").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_add_mastodon_service"),
    ]

    operations = [
        migrations.RunPython(add_open_webui, remove_open_webui),
    ]
