"""Remove the tile of the Zellij web client, retired on 2026-11-27.

The owner no longer uses Zellij web (herdr, T3 Code and Claude Desktop replace
it), and ops-control removed its route ``https://zellij.home.xn--wersdrfer-47a.de/``.
Narrowly guarded: only tiles that still link to that retired URL are deleted,
whatever their name; any other tile stays. A logo file the tile referenced stays
in ``MEDIA_ROOT/services/logos/`` (the seed tile had none). The reverse does not
bring the tile back.
"""

from django.db import migrations

ZELLIJ_URL = "https://zellij.home.xn--wersdrfer-47a.de/"


def remove_zellij_tile(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    Service.objects.using(schema_editor.connection.alias).filter(url=ZELLIJ_URL).delete()


def keep_removal(apps, schema_editor):
    """Zellij web is retired: the reverse does not bring its tile back."""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_service_logo_file_index"),
    ]

    operations = [
        migrations.RunPython(remove_zellij_tile, keep_removal),
    ]
