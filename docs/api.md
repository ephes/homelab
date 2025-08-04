# API Reference

This document provides reference information for Homelab's internal APIs and models.

## Models

### Service Model

The core model representing a service in your homelab.

```python
from apps.core.models import Service
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | AutoField | Primary key |
| `name` | CharField(100) | Unique service name |
| `description` | TextField | Optional description |
| `url` | URLField | Service URL |
| `icon` | CharField(50) | Font Awesome icon class |
| `is_active` | BooleanField | Display on dashboard |
| `order` | IntegerField | Display order |
| `created_at` | DateTimeField | Creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |

#### Methods

##### `__str__()`
Returns the service name.

```python
service = Service.objects.get(id=1)
print(service)  # "Nextcloud"
```

#### Manager Methods

##### `objects.active()`
Returns only active services (if implemented).

```python
active_services = Service.objects.filter(is_active=True)
```

#### Meta Options

- `ordering`: `['order', 'name']`
- `verbose_name`: "Service"
- `verbose_name_plural`: "Services"

## Views

### HomeView

Main dashboard view displaying all active services.

```python
from apps.core.views import HomeView
```

#### Attributes

- `model`: Service
- `template_name`: "core/home.html"
- `context_object_name`: "services"

#### Methods

##### `get_queryset()`
Returns all active services ordered by the model's default ordering.

```python
def get_queryset(self):
    return Service.objects.filter(is_active=True)
```

## URLs

### URL Patterns

#### Core URLs (`apps.core.urls`)

| Name | Pattern | View | Description |
|------|---------|------|-------------|
| `core:home` | `/` | HomeView | Main dashboard |

#### Admin URLs

| Pattern | Description |
|---------|-------------|
| `/admin/` | Django admin interface |
| `/admin/core/service/` | Service management |

## Template Context

### Home Template

The home template receives the following context:

```python
{
    'services': QuerySet[Service],  # Active services
    'user': User,                   # Current user
    'request': HttpRequest,         # Current request
}
```

## Forms

### Service Form (Admin)

The admin interface uses Django's ModelForm for Service:

```python
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['order', 'name']
    list_editable = ['order', 'is_active']
```

## Settings

### Core Settings

Key settings affecting the application:

| Setting | Description | Default |
|---------|-------------|---------|
| `DEBUG` | Debug mode | `True` (development) |
| `ALLOWED_HOSTS` | Allowed hostnames | `['localhost', '127.0.0.1']` |
| `DATABASES` | Database configuration | SQLite |
| `STATIC_URL` | Static files URL | `/static/` |
| `MEDIA_URL` | Media files URL | `/media/` |

### Custom Settings

| Setting | Description | Usage |
|---------|-------------|-------|
| `ADMIN_URL` | Admin panel URL | Security through obscurity |

## Management Commands

### Built-in Commands

```bash
# Database
python manage.py migrate
python manage.py makemigrations
python manage.py dbshell

# Users
python manage.py createsuperuser
python manage.py changepassword

# Static files
python manage.py collectstatic

# Data
python manage.py dumpdata core.service
python manage.py loaddata services.json
```

### Custom Commands (if implemented)

```bash
# Example custom commands
python manage.py import_services services.csv
python manage.py check_service_health
python manage.py backup_database
```

## Signals

### Available Signals

If implementing signals:

```python
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from apps.core.models import Service

@receiver(post_save, sender=Service)
def service_saved(sender, instance, created, **kwargs):
    if created:
        # New service created
        pass
```

## Middleware

### Active Middleware

1. `SecurityMiddleware` - Security headers
2. `WhiteNoiseMiddleware` - Static file serving
3. `SessionMiddleware` - Session management
4. `CommonMiddleware` - Common operations
5. `CsrfViewMiddleware` - CSRF protection
6. `AuthenticationMiddleware` - User authentication
7. `MessageMiddleware` - Message framework
8. `ClickjackingMiddleware` - Clickjacking protection

## Static Files

### Structure

```
static/
└── core/
    ├── css/
    │   └── style.css
    ├── js/
    │   └── main.js (if added)
    └── images/
        └── logo.png (if added)
```

### CSS Classes

Key CSS classes in `style.css`:

| Class | Description |
|-------|-------------|
| `.services-grid` | Grid container for services |
| `.service-card` | Individual service card |
| `.service-icon` | Icon container |
| `.service-name` | Service title |
| `.service-link` | Link button |

## Database Schema

### Service Table

```sql
CREATE TABLE core_service (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    url VARCHAR(200),
    icon VARCHAR(50),
    is_active BOOLEAN DEFAULT 1,
    order INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE INDEX idx_service_active ON core_service(is_active);
CREATE INDEX idx_service_order ON core_service(order, name);
```

## Extending the API

### Adding New Fields

1. Add field to model:
   ```python
   category = models.CharField(max_length=50, blank=True)
   ```

2. Create migration:
   ```bash
   python manage.py makemigrations
   ```

3. Apply migration:
   ```bash
   python manage.py migrate
   ```

### Adding API Endpoints

To add a REST API:

```python
# apps/core/serializers.py
from rest_framework import serializers
from .models import Service

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'

# apps/core/api_views.py
from rest_framework import viewsets
from .models import Service
from .serializers import ServiceSerializer

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

# apps/core/urls.py
from rest_framework.routers import DefaultRouter
from .api_views import ServiceViewSet

router = DefaultRouter()
router.register('services', ServiceViewSet)

urlpatterns += router.urls
```

## Testing

### Test Fixtures

```python
@pytest.fixture
def service(db):
    """Create a test service."""
    return Service.objects.create(
        name="Test Service",
        description="Test description",
        url="https://test.example.com",
        icon="fas fa-test",
        is_active=True,
        order=10
    )
```

### Test Utils

```python
def create_test_service(**kwargs):
    """Helper to create test services."""
    defaults = {
        'name': 'Test Service',
        'is_active': True,
        'order': 0
    }
    defaults.update(kwargs)
    return Service.objects.create(**defaults)
```

## Performance

### Query Optimization

```python
# Bad - N+1 queries
services = Service.objects.all()
for service in services:
    print(service.related_model.name)

# Good - Single query
services = Service.objects.select_related('related_model').all()
```

### Caching

```python
from django.core.cache import cache

# Cache service list
services = cache.get('active_services')
if not services:
    services = list(Service.objects.filter(is_active=True))
    cache.set('active_services', services, 300)  # 5 minutes
```