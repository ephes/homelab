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
deploy/             # Ansible deployment
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