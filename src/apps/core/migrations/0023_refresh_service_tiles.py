"""Remove tiles for two retired dashboard URLs and rename the Fediverse tile."""

from django.db import migrations
from django.db.models.functions import Now

RETIRED_URLS = (
    "https://open-webui.home.xn--wersdrfer-47a.de/",
    "https://mailgun.home.xn--wersdrfer-47a.de/",
)
FEDIVERSE_URL = "https://fedi.python-podcast.de/"


def refresh_service_tiles(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    services = Service.objects.using(schema_editor.connection.alias)

    if not services.filter(name="GoToSocial").exists():
        # Both seeds use the same icon, so leave it and any owner override in place.
        services.filter(name="Takahe", url=FEDIVERSE_URL).update(
            name="GoToSocial",
            description="Fediverse server (GoToSocial) for python-podcast.de",
            updated_at=Now(),
        )

    services.filter(url__in=RETIRED_URLS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_remove_retired_zellij_tile"),
    ]

    operations = [
        migrations.RunPython(refresh_service_tiles, migrations.RunPython.noop),
    ]
