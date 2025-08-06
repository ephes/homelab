from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Service


class Command(BaseCommand):
    help = "Add default services to the database"

    def handle(self, *args, **options):
        services = [
            {
                "name": "Home Assistant",
                "description": "Smart home automation platform for controlling lights, sensors, and devices",
                "url": "https://homeassistant.home.xn--wersdrfer-47a.de/",
                "icon": "fa-home",
                "order": 1,
            },
            {
                "name": "Nyxmon",
                "description": "System monitoring and metrics dashboard for homelab infrastructure",
                "url": "https://nyxmon.home.xn--wersdrfer-47a.de/",
                "icon": "fa-chart-line",
                "order": 2,
            },
        ]

        with transaction.atomic():
            for service_data in services:
                service, created = Service.objects.update_or_create(name=service_data["name"], defaults=service_data)
                status = "Created" if created else "Updated"
                self.stdout.write(self.style.SUCCESS(f"{status} service: {service.name}"))

        total = Service.objects.count()
        self.stdout.write(self.style.SUCCESS(f"\nTotal services in database: {total}"))
