"""
Production settings for homelab project.
"""

from pathlib import Path

from .base import *  # noqa

# DEBUG
DEBUG = False

# SECRET KEY
SECRET_KEY = env("DJANGO_SECRET_KEY")  # noqa

# ALLOWED HOSTS
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["home.wersdoerfer.de"])  # noqa

# Security - Enabled for Traefik with SSL
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)  # noqa
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# CSRF - Trust the reverse proxy
CSRF_TRUSTED_ORIGINS = [
    "https://home.wersdoerfer.de",
    "https://*.home.wersdoerfer.de",
]

# Static files - use Whitenoise for production
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("DJANGO_CACHE_LOCATION", default="/tmp/homelab_cache"),  # noqa
        "TIMEOUT": 600,
        "OPTIONS": {"MAX_ENTRIES": 10000},
    }
}

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@home.wersdoerfer.de")  # noqa
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)  # noqa

# Media files - override base to use correct path in production
MEDIA_ROOT = Path("/home/homelab/site/media")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security.DisallowedHost": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "homelab": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
