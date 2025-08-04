"""
Tests for core app models.
"""

import pytest
from django.db import IntegrityError

from apps.core.models import Service


@pytest.mark.django_db
class TestServiceModel:
    """Test the Service model."""

    def test_service_creation(self):
        """Test creating a service."""
        service = Service.objects.create(
            name="Test Service",
            description="A test service",
            url="https://example.com",
            icon="fas fa-test",
            is_active=True,
            order=1,
        )
        assert service.pk is not None
        assert str(service) == "Test Service"

    def test_service_defaults(self):
        """Test service default values."""
        service = Service.objects.create(name="Test Service")
        assert service.description == ""
        assert service.url == ""
        assert service.icon == ""
        assert service.is_active is True
        assert service.order == 0

    def test_service_unique_name(self):
        """Test that service names must be unique."""
        Service.objects.create(name="Test Service")
        with pytest.raises(IntegrityError):
            Service.objects.create(name="Test Service")

    def test_service_ordering(self):
        """Test that services are ordered by order field, then name."""
        service3 = Service.objects.create(name="Charlie", order=1)
        service1 = Service.objects.create(name="Alpha", order=0)
        service2 = Service.objects.create(name="Bravo", order=0)

        services = list(Service.objects.all())
        assert services == [service1, service2, service3]
