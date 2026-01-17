from django.db import migrations


def update_open_webui(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="Open WebUI").update(
        url="https://open-webui.home.xn--wersdrfer-47a.de/",
        icon="fas fa-comments",
        is_active=True,
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_add_open_webui_service"),
    ]

    operations = [
        migrations.RunPython(update_open_webui, noop_reverse),
    ]
