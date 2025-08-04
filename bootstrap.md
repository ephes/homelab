# Homelab Project Bootstrap Plan

## ✅ Current Status

The Homelab project has been successfully implemented with the following features:

### Completed Features

1. **Project Structure** ✅
   - All code in `src/` directory
   - Tests in `tests/` at project root
   - Documentation in `docs/`
   - Deployment configuration in `deploy/` (partial)
   - .vault_password file for secrets

2. **Core Technologies** ✅
   - Django 5.0+ with Python 3.12+
   - SQLite database
   - Whitenoise for static files
   - Granian for production ASGI/WSGI
   - uv for package management

3. **Development Tools** ✅
   - Justfile with all essential commands
   - Pre-commit hooks with Ruff
   - Pytest for testing (all tests passing)
   - Django Debug Toolbar
   - Sphinx documentation with Furo theme

4. **Core Application** ✅
   - Service model for managing home services
   - Admin interface configured
   - Responsive dashboard with Font Awesome icons
   - Static files and templates

5. **Documentation** ✅
   - Streamlined documentation (6 essential pages)
   - Quick start guide
   - Configuration reference
   - Deployment guide
   - Usage instructions
   - Development guide
   - Troubleshooting

### Project Commands

```bash
just            # Show available commands
just install    # Install dependencies
just dev        # Start development server
just test       # Run tests (all passing)
just lint       # Run linting
just docs       # Build documentation
just deploy     # Deploy to production (pending)
```

## 🚧 Next Steps: Deployment to macmini

### 1. Deployment Setup (In Progress)
Based on nyxmon's approach, create deployment for macmini.fritz.box:10010:

#### Files to create in `deploy/`:
- `ansible.cfg` - Ansible configuration
- `vars.yml` - Public variables (port: 10010)
- `secrets.yml` - Encrypted secrets (with .vault_password)
- `inventory/hosts.yml` - Define macmini host
- `host_vars/macmini.yml` - Host-specific variables
- `deploy.yml` - Main deployment playbook
- `templates/systemd.service.j2` - Systemd service
- `templates/env.template.j2` - Production .env file

#### Key differences from nyxmon:
- Single deployment target (no staging/production split)
- Port 10010 instead of 10017
- Project name "homelab" instead of "nyxmon"
- Username "homelab" instead of "nyxmon"

### 2. Later: Traefik Configuration
- Add external access via home.wersdörfer.de
- Configure SSL/TLS with Traefik
- Set up proper domain routing

### 3. Optional Enhancements
- Add more service fields (categories, tags)
- Service health monitoring
- Backup automation
- API endpoints
- Search functionality

## Original Implementation Plan

## Phase 2: Django Configuration

### 2.1 Create Django Settings
- `src/config/settings/base.py` - Common settings
  - SQLite database configuration
  - Basic Django apps
  - Middleware setup
  - Templates configuration
  - Static files with Whitenoise
  
- `src/config/settings/local.py` - Development
  - DEBUG = True
  - django-debug-toolbar
  - Local SQLite database
  
- `src/config/settings/production.py` - Production
  - DEBUG = False
  - Security settings
  - Whitenoise for static files
  - File-based cache
  - Secure headers

### 2.2 Create Core Files
- `src/config/__init__.py`
- `src/config/urls.py` - URL configuration
- `src/config/wsgi.py` - WSGI application
- `manage.py` - Django management script

### 2.3 Environment Configuration
- Create `.env.example` with all required variables
- Document each variable's purpose

## Phase 3: Core App Development

### 3.1 Create Core App Structure
- `src/apps/__init__.py`
- `src/apps/core/__init__.py`
- `src/apps/core/apps.py` - App configuration
- `src/apps/core/models.py` - Initial models
- `src/apps/core/views.py` - Basic views
- `src/apps/core/urls.py` - URL patterns
- `src/apps/core/admin.py` - Admin interface

### 3.2 Create Base Templates
- `src/apps/core/templates/base.html` - Base template
- `src/apps/core/templates/core/home.html` - Homepage
- Basic CSS in `src/apps/core/static/core/css/style.css`

### 3.3 Initial Migration
- Run `just db-migrate` to create initial migrations
- Apply migrations to set up database

## Phase 4: Testing Setup

### 4.1 Configure Testing
- `src/config/settings/test.py` - Test settings
- `tests/conftest.py` - Pytest configuration
- `tests/__init__.py`

### 4.2 Create Initial Tests
- `tests/core/test_views.py` - View tests
- `tests/core/test_models.py` - Model tests
- Ensure tests can run with `just test`

## Phase 5: Deployment Configuration

### 5.1 Ansible Setup
Based on nyxmon's approach:
- `deploy/ansible.cfg` - Ansible configuration
- `deploy/inventory/hosts.yml` - Define macmini host
- `deploy/vars.yml` - Public variables
- `deploy/secrets.yml` - Encrypted secrets

### 5.2 Host Configuration
- `deploy/host_vars/production.yml`:
  ```yaml
  fqdn: "home.wersdoerfer.de"
  deploy_environment: "production"
  host_name: macmini
  ```

### 5.3 Deployment Playbook
Create `deploy/deploy.yml` with tasks for:
- Creating application user
- Setting up directory structure
- Syncing code (excluding db.sqlite3)
- Creating virtual environment with uv
- Installing dependencies
- Setting up systemd service
- Managing static files
- Database migrations
- Service restart

### 5.4 Service Templates
- `deploy/templates/systemd.service.j2` - Systemd unit
- `deploy/templates/env.template.j2` - Production .env
- Adapt from nyxmon's SQLite approach

## Phase 6: Documentation

### 6.1 Create README.md
- Project description
- Quick start guide
- Development setup
- Deployment instructions

### 6.2 Create docs structure
- `docs/index.md` - Documentation home
- `docs/development.md` - Development guide
- `docs/deployment.md` - Deployment guide
- `docs/architecture.md` - Architecture decisions

## Implementation Order

1. **Start Here**: Create pyproject.toml and justfile
2. **Basic Django**: Set up minimal Django project with settings
3. **Core App**: Create core app with homepage
4. **Testing**: Ensure tests work
5. **Deployment**: Create Ansible playbooks
6. **Documentation**: Document as you go

## Success Criteria

- [ ] Django development server runs with `just dev`
- [ ] Tests pass with `just test`
- [ ] SQLite database works in development
- [ ] Static files served correctly
- [ ] Can deploy to macmini with Ansible
- [ ] Production runs on home.wersdoerfer.de
- [ ] All commands documented in justfile

## Notes

- Keep it simple initially - add features incrementally
- Use SQLite from the start (no PostgreSQL migration needed)
- Ensure all paths follow the src/ structure
- Test deployment early and often
- Document deployment secrets needed