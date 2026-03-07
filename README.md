# Homelab

A Django application for managing home infrastructure and services.

## Features

- Dashboard for all home services
- Service management with custom logos and icons
- SQLite database for simplicity
- Responsive design
- Admin interface for easy management
- Default services with pre-configured logos/icons, including Graphyard and Grafana

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for package management

### Development Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd homelab
   ```

2. Install dependencies:
   ```bash
   just install
   ```

3. Copy environment file:
   ```bash
   cp .env.example .env
   ```

4. Run migrations:
   ```bash
   just db-migrate
   ```

5. Create a superuser:
   ```bash
   just createsuperuser
   ```

6. Add default services with logos/icons:
   ```bash
   just manage add_default_services
   ```

7. Start the development server:
   ```bash
   just dev
   ```

8. Access the application at http://localhost:8000

## Available Commands

Run `just` to see all available commands:

- `just dev` - Start development server
- `just test` - Run tests
- `just lint` - Run linting
- `just format` - Format code
- `just shell` - Django shell with extensions
- `just db-migrate` - Create and apply migrations
- `just deploy` - Deploy to production

## Testing

Run tests with:
```bash
just test
```

Run tests with coverage:
```bash
just coverage
```

## Documentation

Comprehensive documentation is available in the `docs/` directory and can be built using Sphinx.

### Building Documentation

```bash
# Build HTML documentation
just docs

# Auto-rebuild on changes (development)
just docs-serve
```

### Documentation Topics

- **[Quick Start](docs/quickstart.md)** - Get up and running quickly
- **[Installation](docs/installation.md)** - Detailed installation guide
- **[Configuration](docs/configuration.md)** - All configuration options
- **[Usage Guide](docs/usage.md)** - How to use Homelab
- **[Services](docs/services.md)** - Managing services
- **[Admin Guide](docs/admin.md)** - Django admin interface
- **[Development](docs/development.md)** - Contributing to Homelab
- **[Testing](docs/testing.md)** - Running and writing tests
- **[Deployment](docs/deployment.md)** - Production deployment

### Online Documentation

After building, documentation is available at `docs/_build/html/index.html`

## Deployment

The application is deployed to macmini.fritz.box (home.wersdoerfer.de) using Ansible.

To deploy:
```bash
just deploy
```

## Project Structure

```text
homelab/
├── src/                  # Source code
│   ├── config/           # Django settings
│   └── apps/             # Django applications
│       └── core/         # Core application
├── tests/                # Test files
├── deploy/               # Deployment configuration
├── docs/                 # Documentation
├── manage.py             # Django management script
├── justfile              # Command runner
└── pyproject.toml         # Project dependencies
```

## License

This project is private and proprietary.
