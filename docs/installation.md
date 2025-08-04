# Installation

This guide covers the detailed installation process for Homelab.

## System Requirements

### Minimum Requirements

- Python 3.12 or higher
- 512MB RAM
- 100MB disk space
- SQLite 3.x

### Recommended Requirements

- Python 3.13
- 1GB RAM
- 1GB disk space for growth
- Modern web browser

## Installation Methods

### Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is the recommended package manager for this project.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repository-url>
cd homelab

# Install dependencies
just install
```

### Manual Installation

If you prefer not to use the justfile:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Configuration

### Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Secret key for Django | Auto-generated |
| `DJANGO_DEBUG` | Debug mode | `True` (development) |
| `DATABASE_URL` | Database connection | `sqlite:///db.sqlite3` |
| `DJANGO_ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` |

### Database Setup

Initialize the database:

```bash
# Create migrations
just manage makemigrations

# Apply migrations
just manage migrate

# Create superuser
just manage createsuperuser
```

### Static Files

In development, static files are served automatically. For production:

```bash
just collectstatic
```

## Verification

Verify your installation:

```bash
# Run tests
just test

# Check Django configuration
just check

# Start development server
just dev
```

If everything is working, you should be able to access:
- http://localhost:8000 - Main dashboard
- http://localhost:8000/admin/ - Admin interface

## Troubleshooting

### Common Issues

**Port already in use**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

**Module not found errors**
```bash
# Ensure you're in the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Reinstall dependencies
uv sync
```

**Database errors**
```bash
# Reset database (WARNING: deletes all data)
rm db.sqlite3
just db-migrate
```

### Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review the logs in `logs/`
3. Open an issue on the repository