# Development

## Setup

```bash
git clone <repo>
cd homelab
just install
just db-migrate
just createsuperuser
just dev
```

## Project Structure

```
src/
├── config/         # Django settings
├── apps/           # Applications
│   └── core/       # Main app
tests/              # Test files
docs/               # Documentation
```

## Common Tasks

```bash
# Database
just db-migrate     # Run migrations
just shell          # Django shell
just db-shell       # SQLite shell

# Testing
just test           # Run tests
just coverage       # With coverage
just lint           # Code linting

# Development
just dev            # Start server
just format         # Format code
```

## Adding Features

1. Create/modify models in `src/apps/core/models.py`
2. Run `just db-migrate`
3. Update admin in `src/apps/core/admin.py`
4. Add tests in `tests/`
5. Run `just test`

## Code Style

- Ruff for linting/formatting
- 120 character line length
- Pre-commit hooks run automatically

## Testing

```python
# tests/core/test_models.py
@pytest.mark.django_db
def test_service_creation():
    service = Service.objects.create(name="Test")
    assert service.is_active
```

## Git Workflow

```bash
git checkout -b feature/my-feature
# Make changes
just test
git commit -m "feat: add new feature"
git push origin feature/my-feature
```

## Debugging

- Django Debug Toolbar enabled in development
- Use `breakpoint()` for debugging
- Check logs with `just logs`

## Development dependency security

The November 2026 lock refresh updates filelock to 4.2.1, Starlette to 1.3.1
and virtualenv to 21.14.10, plus virtualenv's required distlib and packaging
versions. Version 21.14.10 also fixes CVE-2026-113713. These findings affect
pre-commit environments and live documentation tooling; they are not evidence of a Django request exploit. Application
requirements and Django's locked version are unchanged. Packaging is shared
with Gunicorn and is updated to satisfy virtualenv's minimum.

After changing this tooling, run the isolated checks in [Testing](https://github.com/ephes/homelab/blob/main/docs/testing.md)
and build the documentation with `uv run --frozen sphinx-build -b html docs docs/_build/html`.

The refreshed frozen lock also passed a synthetic, in-memory live-docs smoke
check: HTML delivery with reload-script injection, websocket connection and a
`refresh` message. No listening socket or external service was used.
