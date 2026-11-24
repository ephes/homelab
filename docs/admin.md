# Admin Interface Guide

This guide covers using Django's admin interface to manage Homelab.

## Accessing the Admin

### Login

1. Navigate to `/admin/` (or your custom admin URL)
2. Enter your superuser credentials
3. Click "Log in"

### Failed-login limit

Failed logins are limited (`apps.core.login_throttle`), because LAN and
Tailscale clients reach the admin login without Traefik basic auth:

- 5 failures per username and client address within 15 minutes;
- 30 failures per client address, for all usernames, within 15 minutes;
- 100 failures per network (IPv4 /24, IPv6 /64) within 15 minutes, because one
  client can take many addresses in its network. Tailscale addresses
  (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`) have no network budget: each node has
  one address, which Tailscale authenticates.

Once a budget is used up, every login it covers is refused with the usual
"Please enter the correct username and password" message, even with the correct
password, until the 15-minute window ends: from that address for that username,
from that address for all usernames, or from every address in that network.
The client address is the one Traefik appended to `X-Forwarded-For`. A
successful login clears the username budget for its address. A database error
during reservation shows the usual login error before any password check. The
application logs a fixed diagnostic when logging is available. If a database
error prevents the refund after a correct password, the attempt stays charged
and the admin shows the usual login error even if logging fails. When logging
is available, the application records the original database error.

The username and address budgets use the exact address, so a few failures on
one LAN device do not lock out the others. The network budget is shared on
purpose: all LAN devices use one IPv4 /24 and one IPv6 /64, so a LAN device
that keeps failing from 4 or more addresses can lock every LAN client out of
the admin login for the rest of the window (and again in the next one). Logins
over Tailscale are not affected; use Tailscale, or wait for the window to end. The limits
are the `HOMELAB_LOGIN_*` settings in `config/settings/base.py`
(see [settings](settings.md)); the budgets live in the `LoginThrottleBucket`
table and expire on their own. Each login attempt prunes up to 100 expired rows
in a sweep, including attempts refused by a full budget. A refused attempt
leaves the active budgets unchanged.

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

Change forms and quick edits carry the revision from when the page was opened.
If another save changed the service, submission shows a conflict with your entered
values retained; it does not overwrite the newer row or store a replacement logo.
Reload the page, compare the current values, and reapply your changes (select an
upload again if needed). A stale row in a quick-edit batch prevents the whole batch
from saving. Missing revisions also require a reload, including pages opened before
this feature was deployed. The revision is checked under a database write lock
held through the save. This protects admin saves against writers that advance
`updated_at` (normal model saves); direct queryset updates must update that timestamp
too to participate in conflict detection.

Single-service and quick-edit submissions load rows, check revisions and save
on the database selected by the service write router. Single-service edits
also validate name uniqueness and handle logo retirement and failed uploads on
that alias. Adding a service or submitting a save-as-new request uses the same
write database for name uniqueness, the new row and failed-upload cleanup.
Opening the change page or list follows the read router. If the
page shows an older revision from a replica, the writer rejects the submission
as a conflict.

When a quick edit fails validation, the list keeps the submitted revisions with
the entered values. Correcting a field error lets you retry the batch, and any
stale row still requires an explicit reload before you can save.

A database failure while saving a valid quick-edit batch also rolls back the
entire batch, including revisions and pending logo cleanup callbacks. Reload the
list after a failed request before retrying to pick up any intervening saves by
another editor; rollback itself leaves the original revision valid for retry.

SQLite uses `IMMEDIATE` transactions so overlapping admin writes wait at
transaction entry, before reading the service. After the winner commits, the
other request validates its stale revision and shows a conflict. The normal
SQLite lock timeout still bounds the wait; exceptionally long transactions can
exhaust it. Real file-backed concurrent request tests cover change forms,
replacement logo storage, and all-or-nothing quick-edit batches in CI.

### Deleting Services

**Single deletion**:
1. Open the service
2. Click "Delete" button
3. Confirm deletion

The single-service confirmation is signed and bound to the displayed revision,
service ID, database and signed-in user. It expires after one hour and accepts
at most 128 KiB of confirmation data. Missing, altered or stale confirmations
return to the service list with a reload message before any audit entry, deletion
or logo cleanup. Reload and open Delete again to inspect and confirm the current
service. Pages opened before this protection was deployed must also be reloaded.
The deletion transaction claims the revision and deletes the service on the
database bound to the confirmation. Logo retirement waits for that database to
commit and checks for references there. Normal saves must advance `updated_at`,
as described for editing above.

**Bulk deletion**:
1. Check boxes next to services
2. Select "Delete selected services" from actions
3. Confirm deletion

Bulk confirmation uses the same signature, user/database binding, one-hour expiry
and 128 KiB token limit. A batch contains at most **500 services**; narrow a larger
selection first. The displayed ID/revision set is fixed even when using "Select
all": services created later are not added to the confirmed batch. If any row
changed or disappeared, or submitted IDs were omitted, added or duplicated, the
whole batch is refused before audit entries, deletion or logo retirement. Reload,
select the current services and inspect a new confirmation. Every row is claimed
on the writer database in one transaction before any destructive effects.

### Logo upload size

Admin logo uploads must be at most **1 MiB (1,048,576 bytes)**. Oversize files
produce a logo field error and preserve the existing service and logo. The
[configuration guide](configuration.md#admin-logo-upload-budget) describes the
actual-byte checks and their scope.

### Logo file cleanup

Replacing or clearing a logo, or deleting services individually or in bulk,
retires the old uploaded file after the database transaction commits. The file
is kept if any Service still references its storage name at cleanup time.
Cleanup checks all distinct, nonempty logo names in a confirmed selection in one
database query. If that query fails, cleanup falls back to checking each logo
individually. Migration `0021_service_logo_file_index` adds a non-unique index
for both lookups. Multiple services can share the same exact storage name.
Rolled-back admin changes preserve the old file; replacement uploads remain
available after successful saves. If the admin change-form transaction fails while
writing an upload, saving its row, or saving related/admin records, the new upload
is removed after rollback. Names are reserved through storage before bytes are
copied. A reported short write aborts the upload before the file is attached to
the service. Cleanup removes only this save's allocation and preserves old and
shared logos. Reference checks and commit callbacks use
the Service write database bound to the save or delete, so rows on
another alias do not determine ownership. The two-alias regression
also covers a failure after the service row commits: cleanup checks the recorded
upload write alias and keeps the file while the committed row references it.
The command is documented in [Testing](testing.md#media-descriptor-and-routed-admin-logo-regressions).

This applies to future admin actions only, not direct model/queryset changes or
historical orphan files. It cannot compensate a rollback in a caller-owned outer
transaction after the admin view has returned successfully. Storage cleanup failures
are logged and never hide the original save error or undo a committed database
change; failed cleanup may require a manual retry.

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
