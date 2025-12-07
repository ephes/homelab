from django.db import migrations


def add_snappymail(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.update_or_create(
        name="SnappyMail",
        defaults={
            "description": "Self-hosted webmail client for IMAP/SMTP access",
            "url": "https://webmail.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-envelope",
            "is_active": True,
            "order": 6,
        },
    )


def remove_snappymail(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.filter(name="SnappyMail").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_add_default_services"),
    ]

    operations = [
        migrations.RunPython(add_snappymail, remove_snappymail),
    ]
