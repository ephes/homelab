"""Switch the Heis and Marina dashboard tiles to their production sites."""

from django.db import migrations
from django.db.models import Case, F, TextField, Value, When
from django.db.models.functions import Now

PROJECT_SITES = (
    ("Heis", "https://heis.staging.django-cast.com", "https://fabian-heis.de/"),
    ("Marina", "https://marina.staging.django-cast.com", "https://marina-adler.de/"),
)


def switch_client_tiles_to_production(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    services = Service.objects.using(schema_editor.connection.alias)

    for project, staging_url, production_url in PROJECT_SITES:
        name = f"Projekt {project}"
        if not services.filter(name=name).exists():
            services.filter(name=f"{name} (Staging)", url__in=(staging_url, f"{staging_url}/")).update(
                name=name,
                url=production_url,
                description=Case(
                    When(
                        description=f"Client project staging site for {project}",
                        then=Value(f"Client project production site for {project}"),
                    ),
                    default=F("description"),
                    output_field=TextField(),
                ),
                updated_at=Now(),
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_refresh_service_tiles"),
    ]

    operations = [
        migrations.RunPython(switch_client_tiles_to_production, migrations.RunPython.noop),
    ]
