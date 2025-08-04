"""
Test settings for homelab project.
"""

from .base import *  # noqa

# DEBUG
DEBUG = False

# Testing
TESTING = True

# Use in-memory SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Password hashers - use faster hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Media files
MEDIA_ROOT = BASE_DIR / "test_media"  # noqa


# Disable migrations for tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Static files
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
