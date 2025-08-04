# Configuration

## Environment Variables

Copy `.env.example` to `.env` and adjust:

```bash
# Essential Settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True                        # False in production
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 # Your domain in production
DATABASE_URL=sqlite:///db.sqlite3        # SQLite default

# Production Only
DJANGO_ADMIN_URL=secret-admin/           # Change from default
DJANGO_CACHE_LOCATION=/var/cache/homelab # Cache directory
```

## Service Management

Add services via admin panel with:
- **Name**: Service display name
- **URL**: Full URL (include https://)
- **Icon**: Font Awesome class (e.g., `fas fa-cloud`)
- **Order**: Display position (lower = first)

Common icons:
- `fas fa-cloud` - Cloud storage
- `fas fa-server` - Generic server
- `fas fa-shield-alt` - Security
- `fas fa-home` - Home automation
- `fab fa-docker` - Docker

## Production Security

Essential production settings:
```bash
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
SECRET_KEY=<generate-new-key>
SECURE_SSL_REDIRECT=True
```

Run security check:
```bash
just manage check --deploy
```