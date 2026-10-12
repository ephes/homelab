"""
Retired settings module.

This package is the leftover of the original ``django-admin startproject``
layout. Its settings carried a fixed development secret key and
``DEBUG = True`` and did not install the homelab application. The settings
that run the project live in ``src/config/settings``.
"""

from django.core.exceptions import ImproperlyConfigured

raise ImproperlyConfigured(
    "homelab.settings is retired and must not be used. Set DJANGO_SETTINGS_MODULE to "
    "config.settings.production (or config.settings.local / config.settings.test) and "
    "serve the application from src.config.wsgi:application."
)
