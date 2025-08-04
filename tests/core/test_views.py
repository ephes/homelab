"""
Tests for core app views.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHomeView:
    """Test the home view."""

    def test_home_view_status_code(self, client):
        """Test that home view returns 200 status code."""
        url = reverse("core:home")
        response = client.get(url)
        assert response.status_code == 200

    def test_home_view_uses_correct_template(self, client):
        """Test that home view uses the correct template."""
        url = reverse("core:home")
        response = client.get(url)
        assert "core/home.html" in [t.name for t in response.templates]

    def test_home_view_displays_services(self, client, service):
        """Test that home view displays active services."""
        url = reverse("core:home")
        response = client.get(url)
        assert service.name in response.content.decode()
        assert service.description in response.content.decode()

    def test_home_view_filters_inactive_services(self, client, service):
        """Test that home view only shows active services."""
        # Make service inactive
        service.is_active = False
        service.save()

        url = reverse("core:home")
        response = client.get(url)
        assert service.name not in response.content.decode()

    def test_home_view_shows_no_services_message(self, client):
        """Test that home view shows message when no services exist."""
        url = reverse("core:home")
        response = client.get(url)
        assert "No services configured yet" in response.content.decode()
