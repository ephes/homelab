from django.db import migrations


def add_cms_services(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.using(schema_editor.connection.alias).get_or_create(
        name="Family Blog CMS",
        defaults={
            "description": "Wagtail admin for the family blog",
            "url": "https://wersdoerfer.de/cms",
            "icon": "fas fa-feather-alt",
            "is_active": True,
            "order": 15,
        },
    )
    Service.objects.using(schema_editor.connection.alias).get_or_create(
        name="Python Podcast CMS",
        defaults={
            "description": "Wagtail admin for python-podcast.de",
            "url": "https://python-podcast.de/cms",
            "icon": "fas fa-podcast",
            "is_active": True,
            "order": 16,
        },
    )


def remove_cms_services(apps, schema_editor):
    """Retain rows: these historical seeds did not record creation ownership."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_add_fractal_ipmi_service"),
    ]

    operations = [
        migrations.RunPython(add_cms_services, remove_cms_services),
    ]
