# Models Reference

Detailed documentation of all models in the Homelab application.

## Core Models

### Service

The `Service` model represents a service or application in your homelab.

#### Model Definition

```python
from django.db import models

class Service(models.Model):
    """Represents a service or application in the homelab."""
    
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique name for the service"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the service"
    )
    
    url = models.URLField(
        blank=True,
        help_text="Full URL to access the service"
    )
    
    icon = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fas fa-cloud')"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether to display this service on the dashboard"
    )
    
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the service was first added"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the service was last modified"
    )
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Service"
        verbose_name_plural = "Services"
    
    def __str__(self):
        return self.name
```

#### Field Details

##### name
- **Type**: CharField
- **Max Length**: 100 characters
- **Required**: Yes
- **Unique**: Yes
- **Purpose**: Primary identifier for the service
- **Example**: "Nextcloud", "Home Assistant"

##### description
- **Type**: TextField
- **Required**: No
- **Purpose**: Detailed information about the service
- **Example**: "Personal cloud storage and file synchronization service"

##### url
- **Type**: URLField
- **Required**: No
- **Validation**: Must be a valid URL with protocol
- **Purpose**: Direct link to access the service
- **Example**: "https://cloud.example.com:8080"

##### icon
- **Type**: CharField
- **Max Length**: 50 characters
- **Required**: No
- **Purpose**: Font Awesome icon class for visual identification
- **Format**: "prefix fa-iconname"
- **Example**: "fas fa-cloud", "fab fa-docker"

##### is_active
- **Type**: BooleanField
- **Default**: True
- **Purpose**: Control visibility on dashboard without deletion
- **Use Case**: Temporarily hide services during maintenance

##### order
- **Type**: IntegerField
- **Default**: 0
- **Purpose**: Control display position on dashboard
- **Strategy**: Use increments of 10 for easy reordering

##### created_at
- **Type**: DateTimeField
- **Auto Set**: On creation
- **Purpose**: Track when service was added
- **Timezone**: Uses Django's timezone settings

##### updated_at
- **Type**: DateTimeField
- **Auto Set**: On every save
- **Purpose**: Track last modification
- **Timezone**: Uses Django's timezone settings

#### Model Methods

##### `__str__()`
Returns the service name for string representation.

```python
service = Service.objects.get(id=1)
print(service)  # Output: "Nextcloud"
```

#### Model Meta Options

##### ordering
- **Value**: `['order', 'name']`
- **Effect**: Services are sorted by order first, then alphabetically
- **Override**: Can be overridden in queries

##### verbose_name
- **Value**: "Service"
- **Usage**: Display name in Django admin (singular)

##### verbose_name_plural
- **Value**: "Services"
- **Usage**: Display name in Django admin (plural)

#### Model Validation

##### Clean Method
You can add custom validation:

```python
def clean(self):
    from django.core.exceptions import ValidationError
    
    # Example: Ensure URL uses HTTPS in production
    if self.url and not self.url.startswith('https://'):
        raise ValidationError({
            'url': 'Service URLs should use HTTPS for security.'
        })
    
    # Example: Validate icon format
    if self.icon and not self.icon.startswith(('fas ', 'far ', 'fab ')):
        raise ValidationError({
            'icon': 'Icon must start with a valid Font Awesome prefix.'
        })
```

#### Model Managers

##### Default Manager
```python
# Get all services
Service.objects.all()

# Get active services
Service.objects.filter(is_active=True)

# Get ordered services
Service.objects.order_by('order', 'name')
```

##### Custom Manager (Example)
```python
class ServiceManager(models.Manager):
    def active(self):
        return self.filter(is_active=True)
    
    def by_category(self, category):
        return self.filter(description__icontains=category)

# In model:
objects = ServiceManager()

# Usage:
Service.objects.active()
Service.objects.by_category('media')
```

#### Database Indexes

Automatically created indexes:
- Primary key index on `id`
- Unique index on `name`

Recommended additional indexes:
```python
class Meta:
    indexes = [
        models.Index(fields=['is_active', 'order']),
        models.Index(fields=['created_at']),
    ]
```

#### Relationships

Currently, Service has no foreign key relationships. If extending:

```python
# Example: Adding categories
class Category(models.Model):
    name = models.CharField(max_length=50)
    
class Service(models.Model):
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services'
    )
```

## Django Built-in Models

### User Model

Homelab uses Django's built-in User model for authentication.

```python
from django.contrib.auth.models import User

# Key fields:
# - username
# - email
# - password
# - is_staff (can access admin)
# - is_superuser (all permissions)
# - is_active
# - date_joined
# - last_login
```

### Group Model

For permission management:

```python
from django.contrib.auth.models import Group

# Create service managers group
group = Group.objects.create(name='Service Managers')
group.permissions.add(
    Permission.objects.get(codename='add_service'),
    Permission.objects.get(codename='change_service'),
    Permission.objects.get(codename='delete_service'),
)
```

## Model Best Practices

### 1. Field Naming
- Use descriptive names
- Follow Python naming conventions
- Avoid abbreviations

### 2. Validation
- Use field validators
- Implement clean() method for complex validation
- Validate at model level, not just forms

### 3. Performance
- Add appropriate indexes
- Use select_related() for foreign keys
- Use prefetch_related() for many-to-many

### 4. Documentation
- Add help_text to fields
- Document complex logic
- Use type hints where appropriate

### 5. Testing
```python
# Test model creation
def test_service_creation():
    service = Service.objects.create(
        name="Test Service",
        url="https://test.example.com"
    )
    assert service.is_active is True
    assert service.order == 0

# Test model validation
def test_service_unique_name():
    Service.objects.create(name="Duplicate")
    with pytest.raises(IntegrityError):
        Service.objects.create(name="Duplicate")
```

## Migration Best Practices

### Creating Migrations
```bash
# After model changes
python manage.py makemigrations -n descriptive_name

# Review before applying
python manage.py showmigrations
python manage.py sqlmigrate core 0001
```

### Data Migrations
```python
# migrations/0002_populate_services.py
from django.db import migrations

def populate_initial_services(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    Service.objects.create(
        name="Dashboard",
        description="System monitoring dashboard",
        url="https://dash.example.com",
        icon="fas fa-tachometer-alt",
        order=10
    )

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(populate_initial_services),
    ]
```

## Future Model Ideas

### ServiceCategory
```python
class ServiceCategory(models.Model):
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=50)
    order = models.IntegerField(default=0)
```

### ServiceStatus
```python
class ServiceStatus(models.Model):
    service = models.OneToOneField(Service, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=True)
    last_checked = models.DateTimeField(auto_now=True)
    response_time = models.IntegerField(null=True)  # milliseconds
```

### ServiceTag
```python
class ServiceTag(models.Model):
    name = models.CharField(max_length=30)
    services = models.ManyToManyField(Service, related_name='tags')
```