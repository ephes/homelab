from django.db import migrations


def add_postfixadmin(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.using(schema_editor.connection.alias).get_or_create(
        name="PostfixAdmin",
        defaults={
            "description": "Mail user and alias management for self-hosted email",
            "url": "https://mailadmin.home.xn--wersdrfer-47a.de/",
            "icon": "fas fa-users-cog",
            "is_active": True,
            "order": 13,
        },
    )


def remove_postfixadmin(apps, schema_editor):
    """Retain rows: these historical seeds did not record creation ownership."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_add_snappymail_service"),
    ]

    operations = [
        migrations.RunPython(add_postfixadmin, remove_postfixadmin),
    ]
