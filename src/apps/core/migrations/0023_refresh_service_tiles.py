"""Remove tiles for two retired dashboard URLs and rename the Fediverse tile."""

from django.db import migrations
from django.db.models import Case, F, TextField, Value, When
from django.db.models.functions import Now

RETIRED_URLS = (
    "https://open-webui.home.xn--wersdrfer-47a.de/",
    "https://mailgun.home.xn--wersdrfer-47a.de/",
)
FEDIVERSE_URLS = (
    "https://fedi.python-podcast.de/",
    "https://fedi.python-podcast.de",
)
TAKAHE_DESCRIPTION = "Fediverse server for python-podcast.de"
GOTOSOCIAL_DESCRIPTION = "Fediverse server (GoToSocial) for python-podcast.de"


def refresh_service_tiles(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    services = Service.objects.using(schema_editor.connection.alias)

    services.filter(url__in=RETIRED_URLS).delete()

    if not services.filter(name="GoToSocial").exists():
        services.filter(name="Takahe", url__in=FEDIVERSE_URLS).update(
            name="GoToSocial",
            description=Case(
                When(description=TAKAHE_DESCRIPTION, then=Value(GOTOSOCIAL_DESCRIPTION)),
                default=F("description"),
                output_field=TextField(),
            ),
            updated_at=Now(),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_remove_retired_zellij_tile"),
    ]

    operations = [
        migrations.RunPython(refresh_service_tiles, migrations.RunPython.noop),
    ]
