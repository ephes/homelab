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

# Production deployment
deploy:
    cd deploy && ansible-playbook deploy.yml --limit production

# Backup production database
backup:
    cd deploy && ansible-playbook backup_database.yml --limit production

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
    @echo "  just deploy       # Deploy to production"
    @echo "  just backup       # Backup production database"