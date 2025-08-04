# Services Management

This guide covers managing services in Homelab - the core feature of the application.

## Understanding Services

Services in Homelab represent any web-based application or tool you run on your home network. Each service has:

- **Name**: Display name
- **Description**: Brief explanation
- **URL**: Direct link to the service
- **Icon**: Visual identifier
- **Status**: Active or inactive
- **Order**: Display position

## Service Model

### Database Schema

```python
class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Field Details

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | String | Yes | Unique service identifier |
| description | Text | No | Detailed service information |
| url | URL | No | Full URL including protocol |
| icon | String | No | Font Awesome icon class |
| is_active | Boolean | Yes | Show/hide on dashboard |
| order | Integer | Yes | Sort position (default: 0) |

## Managing via Admin Interface

### Adding Services

1. Navigate to `/admin/`
2. Click "Services" → "Add Service"
3. Fill in required fields
4. Save

### Bulk Import

For multiple services, use Django's loaddata:

```bash
# Create services.json
[
  {
    "model": "core.service",
    "fields": {
      "name": "Nextcloud",
      "description": "Personal cloud storage",
      "url": "https://cloud.home.local",
      "icon": "fas fa-cloud",
      "is_active": true,
      "order": 10
    }
  }
]

# Import
just manage loaddata services.json
```

## Service Organization

### Categorization Strategy

Use order ranges for categories:

```
0-99:    Infrastructure (DNS, monitoring)
100-199: Media (Plex, Jellyfin)
200-299: Productivity (Nextcloud, Wiki)
300-399: Development (GitLab, Jenkins)
400-499: Home Automation
500+:    Miscellaneous
```

### Naming Conventions

- Use clear, recognizable names
- Include version if relevant: "PostgreSQL 15"
- Avoid abbreviations unless well-known
- Be consistent with capitalization

## Icon Selection Guide

### Icon Categories

**Infrastructure**
- `fas fa-server` - Generic server
- `fas fa-network-wired` - Network services
- `fas fa-shield-alt` - Security/firewall
- `fas fa-chart-line` - Monitoring

**Media & Entertainment**
- `fas fa-film` - Video streaming
- `fas fa-music` - Audio streaming
- `fas fa-images` - Photo galleries
- `fas fa-book` - E-books/reading

**Productivity**
- `fas fa-cloud` - Cloud storage
- `fas fa-calendar` - Calendar services
- `fas fa-tasks` - Task management
- `fas fa-sticky-note` - Notes

**Development**
- `fas fa-code` - Code/IDE
- `fab fa-git-alt` - Git services
- `fab fa-docker` - Containers
- `fas fa-database` - Databases

**Home Automation**
- `fas fa-home` - Smart home
- `fas fa-lightbulb` - Lighting
- `fas fa-thermometer-half` - Climate
- `fas fa-video` - Cameras

### Custom Icons

For services without obvious icons:
1. Search Font Awesome: https://fontawesome.com/search
2. Use generic alternatives:
   - `fas fa-cog` - Settings/configuration
   - `fas fa-cube` - Generic application
   - `fas fa-external-link-alt` - External service

## Advanced Management

### Command Line Management

**List all services**:
```bash
just shell
>>> from apps.core.models import Service
>>> Service.objects.all()
```

**Create service**:
```python
>>> Service.objects.create(
...     name="Pi-hole",
...     description="Network-wide ad blocking",
...     url="http://pihole.local/admin",
...     icon="fas fa-shield-alt",
...     order=10
... )
```

**Update service**:
```python
>>> service = Service.objects.get(name="Pi-hole")
>>> service.icon = "fas fa-ban"
>>> service.save()
```

### Export/Import

**Export current services**:
```bash
just manage dumpdata core.service --indent 2 > services_backup.json
```

**Import services**:
```bash
just manage loaddata services_backup.json
```

## Service Templates

### Common Service Configurations

**Nextcloud**
```json
{
  "name": "Nextcloud",
  "description": "Personal cloud storage and collaboration",
  "url": "https://cloud.example.com",
  "icon": "fas fa-cloud",
  "order": 100
}
```

**Home Assistant**
```json
{
  "name": "Home Assistant",
  "description": "Open source home automation",
  "url": "https://ha.example.com",
  "icon": "fas fa-home",
  "order": 200
}
```

**Portainer**
```json
{
  "name": "Portainer",
  "description": "Docker container management",
  "url": "https://portainer.example.com:9443",
  "icon": "fab fa-docker",
  "order": 50
}
```

## Service Health Monitoring

While Homelab doesn't include built-in health monitoring, you can:

1. **Visual inspection**: Regularly check dashboard links
2. **External monitoring**: Use tools like Uptime Kuma
3. **Manual checks**: Script to verify URLs:

```python
import requests
from apps.core.models import Service

for service in Service.objects.filter(is_active=True):
    try:
        response = requests.head(service.url, timeout=5)
        print(f"✓ {service.name}: {response.status_code}")
    except:
        print(f"✗ {service.name}: Failed")
```

## Best Practices

1. **Keep URLs Updated**: Services may change ports or addresses
2. **Use HTTPS**: When possible, use secure connections
3. **Document Services**: Use descriptions for important notes
4. **Regular Cleanup**: Remove obsolete services
5. **Consistent Icons**: Use similar icons for related services
6. **Logical Ordering**: Group related services together

## Troubleshooting

### Service Not Appearing

Check:
- Is `is_active` set to True?
- Did you restart the server after adding?
- Are there any validation errors?

### Wrong Display Order

- Lower `order` values appear first
- Services with same order sort alphabetically
- Negative values are allowed for priority items

### Icon Not Showing

- Verify Font Awesome class is correct
- Check for typos (e.g., `fa-home` vs `fas fa-home`)
- Ensure Font Awesome version supports the icon