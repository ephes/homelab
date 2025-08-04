# Admin Interface Guide

This guide covers using Django's admin interface to manage Homelab.

## Accessing the Admin

### Login

1. Navigate to `/admin/` (or your custom admin URL)
2. Enter your superuser credentials
3. Click "Log in"

### First-Time Setup

If you haven't created a superuser yet:

```bash
just createsuperuser
```

Follow the prompts to create your admin account.

## Admin Dashboard

### Overview

The admin dashboard shows:
- **Recent actions**: Your latest changes
- **Available models**: Services, Users, Groups

### Navigation

- Click model names to view lists
- Use "Add" buttons to create new items
- Click items to edit
- Use breadcrumbs to navigate back

## Managing Services

### Service List View

The service list shows:
- Name
- URL  
- Active status
- Order
- Created date

Features:
- **Search**: Find services by name or description
- **Filters**: Filter by active status or creation date
- **Sorting**: Click column headers to sort
- **Bulk actions**: Select multiple services for deletion

### Adding a Service

1. Click "Services" → "Add Service"
2. Fill in the fields:

| Field | Description | Example |
|-------|-------------|---------|
| Name* | Service display name | "Nextcloud" |
| Description | Detailed information | "Personal cloud storage and file sync" |
| URL | Full service URL | "https://cloud.example.com" |
| Icon | Font Awesome class | "fas fa-cloud" |
| Is active | Show on dashboard | ✓ Checked |
| Order | Display position | 10 |

3. Click "Save" or:
   - "Save and add another" to add more services
   - "Save and continue editing" to stay on the page

### Editing Services

1. Click on a service name in the list
2. Modify fields as needed
3. Save changes

**Quick Edit**: In the list view, some fields (order, is_active) can be edited inline.

### Deleting Services

**Single deletion**:
1. Open the service
2. Click "Delete" button
3. Confirm deletion

**Bulk deletion**:
1. Check boxes next to services
2. Select "Delete selected services" from actions
3. Confirm deletion

## User Management

### Viewing Users

Navigate to "Users" to see all user accounts.

### Creating Users

1. Click "Add User"
2. Enter username and password
3. Save to continue to full form
4. Set permissions and groups
5. Save

### User Permissions

**Staff status**: Allows admin login
**Superuser status**: Full access to everything

**Specific permissions**:
- Can add/change/delete services
- Can view services

### Groups

Create groups for different permission levels:

1. Click "Groups" → "Add Group"
2. Name the group (e.g., "Service Managers")
3. Select permissions
4. Save

Assign users to groups for easier permission management.

## Advanced Admin Features

### Customizing List Display

The admin is configured to show useful columns:

```python
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['order', 'name']
    list_editable = ['order', 'is_active']
```

### Search Functionality

Search works across multiple fields:
- Service name
- Description

Search tips:
- Partial matches work
- Case-insensitive
- Multiple words search all fields

### Filtering

Available filters:
- **Is active**: Yes/No/All
- **Created at**: Today/Past 7 days/This month/This year

### Bulk Actions

Default actions:
- Delete selected services

Custom actions can be added for:
- Activate/deactivate multiple services
- Export to JSON
- Bulk update fields

## Admin Customization

### Changing Admin URL

For security, change the admin URL in production:

```bash
# .env
DJANGO_ADMIN_URL=secret-admin-panel/
```

### Admin Theme

The default Django admin works well, but you can enhance it:

1. **Django Admin Interface**: Modern theme
2. **Grappelli**: Professional skin
3. **Jazzmin**: Bootstrap-based theme

### Custom Admin Site

For branding:

```python
# apps/core/admin.py
from django.contrib import admin

admin.site.site_header = "Homelab Administration"
admin.site.site_title = "Homelab Admin"
admin.site.index_title = "Welcome to Homelab Admin"
```

## Tips and Tricks

### Keyboard Shortcuts

- `Alt + A` - Add new item
- `Alt + S` - Save
- `Enter` - Submit forms
- `Tab` - Navigate fields

### Quick Actions

1. **Clone a service**: Save as new
2. **Preview changes**: Save and continue editing
3. **History**: View change history for any object

### Power User Features

**Admin URLs**:
- `/admin/core/service/` - Service list
- `/admin/core/service/add/` - Add service directly
- `/admin/core/service/1/change/` - Edit service ID 1

**Export data**:
```bash
# From command line
just manage dumpdata core.service --indent 2
```

## Security Best Practices

1. **Strong passwords**: Use complex admin passwords
2. **Unique admin URL**: Change from default `/admin/`
3. **HTTPS only**: Always use SSL in production
4. **Limit access**: Restrict admin by IP if possible
5. **Regular audits**: Review user permissions
6. **Session timeout**: Configure automatic logout

### Restricting Admin Access

Add to nginx configuration:
```nginx
location /admin/ {
    allow 192.168.1.0/24;  # Local network only
    deny all;
    proxy_pass http://localhost:8001;
}
```

## Troubleshooting

### Can't Log In

1. Check username/password
2. Ensure user has staff status
3. Verify ALLOWED_HOSTS includes your domain
4. Clear browser cookies

### Missing Static Files

If admin looks broken:
```bash
just collectstatic
```

### Permission Denied

Ensure user has:
- Staff status (can access admin)
- Appropriate permissions or superuser status

### Forgotten Password

Reset from command line:
```bash
just manage changepassword <username>
```

## Admin API

### Programmatic Access

Access admin functionality from code:

```python
from django.contrib import admin
from apps.core.models import Service

# Get admin instance
service_admin = admin.site._registry[Service]

# Use admin methods
queryset = Service.objects.all()
service_admin.get_search_results(request, queryset, 'search_term')
```

### Custom Admin Commands

Create management commands for admin tasks:

```bash
just manage promote_user username  # Make user admin
just manage list_services          # List all services
just manage backup_services        # Export services
```

## Best Practices

1. **Regular backups**: Before major changes
2. **Test first**: Try changes in development
3. **Document changes**: Note what you modify
4. **Minimal permissions**: Give users only what they need
5. **Audit logs**: Monitor admin actions
6. **Clean data**: Remove old/unused items

## Extending the Admin

### Adding Custom Views

```python
from django.urls import path
from django.shortcuts import render

class ServiceAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', 
                 self.admin_site.admin_view(self.statistics_view),
                 name='core_service_statistics'),
        ]
        return custom_urls + urls
    
    def statistics_view(self, request):
        context = {
            'total_services': Service.objects.count(),
            'active_services': Service.objects.filter(is_active=True).count(),
        }
        return render(request, 'admin/statistics.html', context)
```

### Custom Actions

```python
@admin.action(description='Mark selected services as inactive')
def make_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)

class ServiceAdmin(admin.ModelAdmin):
    actions = [make_inactive]
```