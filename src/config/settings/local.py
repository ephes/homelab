"""
Local development settings for homelab project.
"""

from .base import *  # noqa

# DEBUG
DEBUG = True

# ALLOWED HOSTS
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Django Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa

MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa

# Debug toolbar configuration
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]

# Django Extensions
INSTALLED_APPS += ["django_extensions"]  # noqa

# Shell Plus configuration
SHELL_PLUS_PRINT_SQL = True
SHELL_PLUS_PRINT_SQL_TRUNCATE = 1000

# Email Backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Static files - use Django's static file serving in development
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
