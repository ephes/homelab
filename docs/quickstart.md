# Quick Start

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
# Clone and setup
git clone <repository-url>
cd homelab
just install

# Configure
cp .env.example .env
just db-migrate
just createsuperuser

# Run
just dev
```

Access at http://localhost:8000

## Adding Services

1. Go to http://localhost:8000/admin/
2. Add Service → Fill in name, URL, and icon
3. View on dashboard

## Common Commands

```bash
just            # Show all commands
just test       # Run tests
just docs       # Build documentation
just deploy     # Deploy to production
```

## Production Deployment

See [deployment guide](deployment.md) for Ansible-based deployment to your server.