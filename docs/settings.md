# Settings Reference

Complete reference for all Django settings used in Homelab.

## Settings Structure

```
src/config/settings/
├── __init__.py
├── base.py        # Common settings for all environments
├── local.py       # Development settings
├── production.py  # Production settings
└── test.py        # Test settings
```

## Base Settings

Settings shared across all environments (from `base.py`).

### Core Django Settings

#### SECRET_KEY
- **Type**: String
- **Default**: Auto-generated for development
- **Production**: Must be set via environment variable
- **Security**: Keep secret, rotate regularly

```python
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-CHANGEME")
```

#### DEBUG
- **Type**: Boolean
- **Default**: False
- **Local**: True
- **Production**: Must be False
- **Warning**: Never enable in production

```python
DEBUG = env("DEBUG", default=False)
```

#### ALLOWED_HOSTS
- **Type**: List
- **Default**: Empty list
- **Production**: Must include your domain
- **Format**: `['example.com', 'www.example.com']`

```python
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
```

### Application Definition

#### INSTALLED_APPS
```python
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = []  # Add third-party apps here

LOCAL_APPS = [
    "apps.core",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
```

#### MIDDLEWARE
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

### Database Configuration

#### DATABASES
```python
DATABASES = {
    "default": env.db(default="sqlite:///db.sqlite3"),
}
```

Environment variable format:
- SQLite: `sqlite:///path/to/db.sqlite3`
- PostgreSQL: `postgres://user:pass@host:port/dbname`
- MySQL: `mysql://user:pass@host:port/dbname`

### Static Files

#### STATIC_URL
- **Default**: `/static/`
- **Purpose**: URL prefix for static files

#### STATIC_ROOT
- **Default**: `BASE_DIR / "staticfiles"`
- **Purpose**: Directory for collected static files

```python
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
```

### Media Files

#### MEDIA_URL
- **Default**: `/media/`
- **Purpose**: URL prefix for uploaded files

#### MEDIA_ROOT
- **Default**: `BASE_DIR / "media"`
- **Purpose**: Directory for uploaded files

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

### Internationalization

```python
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Berlin"  # Adjust to your timezone
USE_I18N = True
USE_TZ = True
```

### Security Settings

#### Password Validators
```python
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
```

## Development Settings

Additional settings for local development (from `local.py`).

### Debug Toolbar

```python
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
```

### Django Extensions

```python
INSTALLED_APPS += ["django_extensions"]
SHELL_PLUS_PRINT_SQL = True
```

### Email Backend

```python
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

## Production Settings

Security and performance settings for production (from `production.py`).

### Security Headers

```python
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
```

### Static Files Storage

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

### Caching

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("DJANGO_CACHE_LOCATION", default="/tmp/homelab_cache"),
        "TIMEOUT": 600,
        "OPTIONS": {
            "MAX_ENTRIES": 10000
        }
    }
}
```

### Email Configuration

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
```

### Logging

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
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
        "homelab": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

## Test Settings

Optimized settings for testing (from `test.py`).

### Test Database

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",  # In-memory database for speed
    }
}
```

### Password Hashing

```python
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # Fast for tests
]
```

### Disable Migrations

```python
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()
```

## Environment Variables

Complete list of environment variables used by Homelab.

### Required in Production

| Variable | Description | Example |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Secret key for cryptographic signing | Random 50+ character string |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `example.com,www.example.com` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_DEBUG` | Enable debug mode | `False` |
| `DATABASE_URL` | Database connection string | `sqlite:///db.sqlite3` |
| `DJANGO_ADMIN_URL` | Admin panel URL path | `admin/` |
| `DJANGO_CACHE_LOCATION` | Cache file location | `/tmp/homelab_cache` |
| `DJANGO_LOG_LEVEL` | Django logging level | `INFO` |
| `HOMELAB_LOG_LEVEL` | App logging level | `DEBUG` |

### Email Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMAIL_HOST` | SMTP server hostname | None |
| `EMAIL_PORT` | SMTP server port | 587 |
| `EMAIL_USE_TLS` | Use TLS for email | `True` |
| `EMAIL_HOST_USER` | SMTP username | None |
| `EMAIL_HOST_PASSWORD` | SMTP password | None |
| `DEFAULT_FROM_EMAIL` | Default sender address | `noreply@example.com` |

## Custom Settings

### Application-Specific Settings

```python
# Admin URL (for security through obscurity)
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

# Custom app settings
HOMELAB_FEATURE_X = env.bool("HOMELAB_FEATURE_X", default=False)
```

### Adding New Settings

1. Define in appropriate settings file
2. Add to environment variables documentation
3. Update `.env.example`
4. Set production values in deployment

## Settings Best Practices

### Security

1. **Never commit secrets** - Use environment variables
2. **Rotate keys regularly** - Especially after team changes
3. **Use strong passwords** - Enforce with validators
4. **Enable HTTPS** - Use SECURE_SSL_REDIRECT
5. **Set security headers** - Use Django's security middleware

### Performance

1. **Enable caching** - Use Redis or file-based cache
2. **Optimize database** - Use connection pooling
3. **Compress static files** - Use Whitenoise compression
4. **Set appropriate timeouts** - Configure CONN_MAX_AGE

### Development

1. **Use different settings** - Separate dev/prod configurations
2. **Enable debug toolbar** - For development only
3. **Use console email** - Avoid sending real emails in dev
4. **Mock external services** - Use test doubles

### Deployment

1. **Validate settings** - Run `check --deploy`
2. **Test configuration** - Deploy to staging first
3. **Monitor errors** - Configure error reporting
4. **Document changes** - Update when adding settings

## Troubleshooting Settings

### Common Issues

**ImproperlyConfigured: The SECRET_KEY setting must not be empty**
- Set DJANGO_SECRET_KEY in environment

**ALLOWED_HOSTS error**
- Add your domain to DJANGO_ALLOWED_HOSTS

**Static files not loading**
- Run `collectstatic` in production
- Check STATIC_ROOT configuration

**Database connection failed**
- Verify DATABASE_URL format
- Check database server is running

### Debug Settings

```python
# Temporarily enable for debugging
print("DEBUG:", settings.DEBUG)
print("DATABASES:", settings.DATABASES)
print("STATIC_ROOT:", settings.STATIC_ROOT)

# Check all settings
python manage.py diffsettings
```