"""
Pytest configuration for homelab project tests.
"""

import os
import sys
from pathlib import Path

import django
import pytest

# Add src directory to Python path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

# Configure Django settings for tests
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")


def pytest_configure():
    """Configure Django settings for pytest."""
    # Setup Django
    django.setup()


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Give all tests access to the database.
    This fixture is automatically used in all tests.
    """
    pass


@pytest.fixture
def client():
    """Provide a Django test client."""
    from django.test import Client

    return Client()


@pytest.fixture
def admin_client(db):
    """Provide a Django test client logged in as an admin."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    User = get_user_model()
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def service(db):
    """Create a test service."""
    from apps.core.models import Service

    return Service.objects.create(
        name="Test Service",
        description="A test service",
        url="https://example.com",
        icon="fas fa-test",
        is_active=True,
        order=1,
    )
