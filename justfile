# Justfile for homelab project development

# Default recipe - show available commands
default:
    @just --list

# Install dependencies
install:
    uv sync
    uv run pre-commit install

# Run development server
dev:
    uv run python manage.py runserver

# Run tests
test:
    uv run pytest

# Run specific test
test-one TEST_PATH:
    uv run pytest {{TEST_PATH}} -v

# Run tests with coverage
coverage:
    uv run pytest --cov --cov-report=html --cov-report=term

# Run linting with pre-commit
lint:
    uvx pre-commit run --all-files

# Format code with ruff
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Django management commands
manage *ARGS:
    uv run python manage.py {{ARGS}}

# Database operations
db-migrate:
    @just manage makemigrations
    @just manage migrate

# Create superuser
createsuperuser:
    @just manage createsuperuser

# Django shell with extensions
shell:
    @just manage shell_plus --print-sql

# Database shell
db-shell:
    @just manage dbshell

# Collect static files
collectstatic:
    @just manage collectstatic --noinput

# Check Django project for issues
check:
    @just manage check --deploy

# Clean up generated files
clean:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type f -name ".DS_Store" -delete
    rm -rf htmlcov/
    rm -rf .pytest_cache/
    rm -rf .coverage
    rm -rf docs/_build/

# Build documentation
docs:
    cd docs && uv run make clean && uv run make html
    @echo "Documentation built at docs/_build/html/index.html"

# Serve documentation with auto-rebuild
docs-serve:
    cd docs && uv run sphinx-autobuild . _build/html --port 8001

# Open documentation in browser
docs-open: docs
    open docs/_build/html/index.html

# Deploy to macmini - app only (default)
deploy:
    cd deploy && ansible-playbook deploy.yml

# Deploy all components
deploy-all:
    cd deploy && ansible-playbook deploy-all.yml

# Deploy only the Django app
deploy-app:
    cd deploy && ansible-playbook deploy-app.yml

# Deploy only DynDNS
deploy-dyndns:
    cd deploy && ansible-playbook deploy-dyndns.yml

# Deploy only Pi-hole DNS server
deploy-pihole:
    cd deploy && ansible-playbook deploy-pihole.yml

# Deploy only Traefik reverse proxy
deploy-traefik:
    cd deploy && ansible-playbook deploy-traefik.yml

# Backup database (SQLite)
backup:
    @echo "Database backup not yet implemented for SQLite"

# Restore database from backup
restore:
    cd deploy && ansible-playbook restore_database.yml --limit production

# Help for common tasks
help:
    @echo "Common tasks:"
    @echo ""
    @echo "Development:"
    @echo "  just dev          # Start development server"
    @echo "  just test         # Run tests"
    @echo "  just lint         # Run linting"
    @echo "  just shell        # Django shell"
    @echo ""
    @echo "Database:"
    @echo "  just db-migrate   # Create and apply migrations"
    @echo "  just db-shell     # Database shell"
    @echo ""
    @echo "Documentation:"
    @echo "  just docs         # Build HTML documentation"
    @echo "  just docs-serve   # Serve docs with auto-rebuild"
    @echo "  just docs-open    # Build and open docs in browser"
    @echo ""
    @echo "Deployment:"
    @echo "  just deploy       # Deploy app only (default)"
    @echo "  just deploy-all   # Deploy all components"
    @echo "  just deploy-app   # Deploy Django app"
    @echo "  just deploy-dyndns # Deploy DynDNS"
    @echo "  just deploy-pihole # Deploy Pi-hole DNS"
    @echo "  just deploy-traefik # Deploy Traefik"
    @echo "  just backup       # Backup production database"
    @echo ""
    @echo "DNS Testing:"
    @echo "  just dns-test     # Test DNS resolution"
    @echo "  just dns-status   # Check DNS server status"

# Test DNS resolution
dns-test:
    @echo "Testing external DNS resolution..."
    @dig +short home.wersdörfer.de @8.8.8.8
    @echo ""
    @echo "Testing local DNS resolution (if configured)..."
    @dig +short home.wersdörfer.de @127.0.0.1 2>/dev/null || echo "Local DNS not configured on this machine"
    @echo ""
    @echo "For full DNS testing on macmini, run:"
    @echo "ssh homelab@macmini.fritz.box './site/bin/test-dns.sh'"

# Check DNS server status on macmini
dns-status:
    ssh root@macmini.fritz.box "pihole status" || echo "Pi-hole not installed or SSH not configured"

# Test Traefik setup
traefik-test:
    @echo "Testing Traefik configuration..."
    @echo ""
    @echo "1. Testing HTTP redirect:"
    curl -I http://home.wersdörfer.de || echo "HTTP not accessible yet"
    @echo ""
    @echo "2. Testing HTTPS:"
    curl -I https://home.wersdörfer.de || echo "HTTPS not accessible yet"
    @echo ""
    @echo "3. Check Traefik status on macmini:"
    ssh root@macmini.fritz.box "systemctl status traefik --no-pager | head -20" || echo "SSH not configured"

# View Traefik logs
traefik-logs:
    ssh root@macmini.fritz.box "journalctl -u traefik -n 50 --no-pager"