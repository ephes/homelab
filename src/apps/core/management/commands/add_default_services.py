from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Service


class Command(BaseCommand):
    help = "Add default services to the database"

    def handle(self, *args, **options):
        # Path to static logos directory where we keep the source logos
        logos_dir = Path(__file__).parent.parent.parent / "static" / "core" / "logos"

        services = [
            {
                "name": "Home Assistant",
                "description": "Smart home automation platform for controlling lights, sensors, and devices",
                "url": "https://homeassistant.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-home",
                "logo_filename": "home-assistant.png",
                "order": 1,
            },
            {
                "name": "Nyxmon",
                "description": "System monitoring and metrics dashboard for homelab infrastructure",
                "url": "https://nyxmon.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-chart-line",
                "logo_filename": "nyxmon.png",
                "order": 2,
            },
        ]

        with transaction.atomic():
            for service_data in services:
                logo_filename = service_data.pop("logo_filename", None)

                service, created = Service.objects.update_or_create(name=service_data["name"], defaults=service_data)

                # Add logo file if specified and file exists
                if logo_filename:
                    logo_path = logos_dir / logo_filename
                    if logo_path.exists() and not service.logo_file:
                        with open(logo_path, "rb") as f:
                            service.logo_file.save(logo_filename, File(f), save=True)
                        self.stdout.write(self.style.SUCCESS(f"Added logo for {service.name}"))

                status = "Created" if created else "Updated"
                self.stdout.write(self.style.SUCCESS(f"{status} service: {service.name}"))

        total = Service.objects.count()
        self.stdout.write(self.style.SUCCESS(f"\nTotal services in database: {total}"))
