# Homelab Django Project

## Project Overview
The homelab project is a Django application for managing home infrastructure and services. It follows the structure of the homepage project but with several key differences:

- **SQLite** database instead of PostgreSQL (following nyxmon's approach)
- **All code in src/** directory structure  
- **Tests in tests/** at project root (not in app directories)
- **Justfile** for all commands (no commands.py)
- **Single production deployment** to macmini.fritz.box (home.wersdörfer.de)

## Project Structure

```
homelab/
├── docs/                      # Documentation
├── src/                       # All source code
│   ├── config/               # Django configuration
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py      # Base settings
│   │   │   ├── local.py     # Local development
│   │   │   ├── production.py # Production settings
│   │   │   └── test.py      # Test settings
│   │   ├── urls.py          # URL configuration
│   │   └── wsgi.py          # WSGI config
│   └── apps/                 # Django applications
│       └── core/            # Core homelab app
│           ├── __init__.py
│           ├── apps.py
│           ├── models.py
│           ├── views.py
│           ├── urls.py
│           ├── admin.py
│           ├── migrations/
│           └── templates/
├── tests/                    # All tests
│   ├── __init__.py
│   ├── conftest.py
│   └── core/
│       └── test_views.py
├── deploy/                   # Deployment configuration
│   ├── ansible.cfg
│   ├── deploy.yml
│   ├── host_vars/
│   │   └── production.yml
│   ├── inventory/
│   │   └── hosts.yml
│   ├── templates/
│   └── vars.yml
├── manage.py                 # Django management script
├── justfile                  # Development commands
├── pyproject.toml           # Project dependencies
├── uv.lock                  # Locked dependencies
├── .env.example             # Environment template
├── README.md                # Project documentation
└── bootstrap.md             # Implementation plan

```

## Key Configuration Details

### Database
- **SQLite** for all environments (development and production)
- Database file: `db.sqlite3` in project root for development
- Production database in deployment directory

### Deployment
- **Single production environment** (no staging)
- **Host**: macmini.fritz.box
- **Domain**: home.wersdörfer.de
- **Server**: Granian (ASGI/WSGI server)
- **Static files**: Whitenoise
- **Process management**: systemd
- **Reverse proxy**: Existing system (likely Traefik)

### Development Tools
- **uv** for Python package management
- **justfile** for command automation
- **Django 5.x** with modern Python (3.12+)
- **django-environ** for environment configuration

## Environment Variables

Required environment variables (see .env.example):

```bash
# Django settings
DJANGO_SETTINGS_MODULE=config.settings.local
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite)
DATABASE_URL=sqlite:///db.sqlite3

# Production-specific
DJANGO_ADMIN_URL=admin/
DJANGO_CACHE_LOCATION=/path/to/cache
```

## Justfile Commands

The justfile should provide these commands:

- `just` - Show available commands
- `just dev` - Start development server
- `just test` - Run tests
- `just lint` - Run linting
- `just manage [command]` - Run Django management commands
- `just db-migrate` - Create and apply migrations
- `just shell` - Django shell
- `just deploy` - Deploy to production
- `just backup` - Backup production database

## Development Workflow

1. **Setup**: `just install` to install dependencies
2. **Database**: `just db-migrate` to setup database
3. **Development**: `just dev` to start server
4. **Testing**: `just test` to run tests
5. **Deployment**: `just deploy` to deploy to production

## Testing Strategy

- Tests live in `tests/` directory at project root
- Use pytest with django-pytest
- Separate test settings in `config.settings.test`
- Coverage reports with pytest-cov

## Security Considerations

- Use django-environ for secure environment variable handling
- SQLite database should be excluded from version control
- Production secrets managed through Ansible vault
- HTTPS enforced in production
- Secure headers via Django security middleware

## Notes for Implementation

1. Start with minimal Django project structure
2. Use SQLite from the beginning (no PostgreSQL)
3. Configure Whitenoise early for static files
4. Set up justfile with essential commands
5. Create deployment playbooks based on nyxmon's SQLite approach
6. Ensure proper file permissions for SQLite in production