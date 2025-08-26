"""
Tests for core app models.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_service_with_logo_file(self):
        """Test that a service can have a logo file."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        logo_file = SimpleUploadedFile("test_logo.svg", svg_content, content_type="image/svg+xml")

        service = Service.objects.create(name="Test Service", logo_file=logo_file)

        assert service.logo_file is not None
        assert "test_logo" in service.logo_file.name

        # Clean up
        service.logo_file.delete()
        service.delete()

    def test_service_logo_file_blank(self):
        """Test that logo_file is optional."""
        service = Service.objects.create(name="Test Service")
        assert not service.logo_file
        assert service.icon == ""

    def test_service_with_icon_fallback(self):
        """Test that icon serves as fallback when no logo is present."""
        service = Service.objects.create(name="Test Service", icon="fas fa-server")
        assert not service.logo_file
        assert service.icon == "fas fa-server"

    def test_service_with_both_logo_and_icon(self):
        """Test that a service can have both logo file and icon."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        logo_file = SimpleUploadedFile("test_logo.svg", svg_content, content_type="image/svg+xml")

        service = Service.objects.create(name="Test Service", logo_file=logo_file, icon="fas fa-server")
        assert service.logo_file is not None
        assert service.icon == "fas fa-server"

        # Clean up
        service.logo_file.delete()
        service.delete()
