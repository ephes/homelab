# Testing Guide

This guide covers testing practices and procedures for Homelab.

## Testing Overview

Homelab uses:
- **pytest** as the test framework
- **pytest-django** for Django integration
- **pytest-cov** for coverage reporting
- **Factory pattern** for test data

## Running Tests

### Basic Commands

```bash
# Run all tests
just test

# Run specific test file
just test-one tests/core/test_models.py

# Run specific test class
just test-one tests/core/test_models.py::TestServiceModel

# Run specific test method
just test-one tests/core/test_models.py::TestServiceModel::test_service_creation

# Run with coverage
just coverage
```

### Test Output

Tests provide verbose output by default:
```
tests/core/test_models.py::TestServiceModel::test_service_creation PASSED [ 11%]
tests/core/test_models.py::TestServiceModel::test_service_defaults PASSED [ 22%]
```

## Writing Tests

### Test Structure

Tests are organized by app:
```
tests/
├── __init__.py
├── conftest.py        # Global fixtures
└── core/              # Core app tests
    ├── __init__.py
    ├── test_models.py # Model tests
    ├── test_views.py  # View tests
    └── test_forms.py  # Form tests (if applicable)
```

### Basic Test Example

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestServiceModel:
    """Test the Service model."""
    
    def test_service_creation(self):
        """Test creating a service."""
        from apps.core.models import Service
        
        service = Service.objects.create(
            name="Test Service",
            description="A test service",
            url="https://example.com"
        )
        
        assert service.pk is not None
        assert str(service) == "Test Service"
        assert service.is_active is True
```

### Using Fixtures

Define reusable test data in `conftest.py`:

```python
@pytest.fixture
def service(db):
    """Create a test service."""
    from apps.core.models import Service
    
    return Service.objects.create(
        name="Test Service",
        description="A test service",
        url="https://example.com",
        icon="fas fa-test",
        is_active=True,
        order=1
    )

@pytest.fixture
def inactive_service(db):
    """Create an inactive test service."""
    from apps.core.models import Service
    
    return Service.objects.create(
        name="Inactive Service",
        is_active=False
    )
```

Use fixtures in tests:
```python
def test_service_display(service):
    """Test service is displayed correctly."""
    assert service.name == "Test Service"
    assert service.is_active is True
```

### Media Isolation

`tests/conftest.py` defines a session-scoped, autouse `isolated_media_root`
fixture that overrides `MEDIA_ROOT` with a per-session pytest temporary
directory. Uploads written during tests (for example the service logos that
`add_default_services` saves) therefore never land in the source tree. Request
the fixture when a test needs the path:

```python
def test_logo_upload(isolated_media_root):
    ...
```

`config/settings/test.py` still sets `MEDIA_ROOT = BASE_DIR / "test_media"`
(`src/test_media/`, gitignored) only as a fallback for code that loads the test
settings outside pytest. If an older checkout left files there, they are safe to
delete.

## Testing Views

### View Test Example

```python
@pytest.mark.django_db
class TestHomeView:
    """Test the home view."""
    
    def test_home_view_status_code(self, client):
        """Test that home view returns 200."""
        url = reverse("core:home")
        response = client.get(url)
        assert response.status_code == 200
    
    def test_home_view_displays_services(self, client, service):
        """Test that home view shows active services."""
        url = reverse("core:home")
        response = client.get(url)
        
        assert service.name in response.content.decode()
        assert service.description in response.content.decode()
    
    def test_home_view_filters_inactive(self, client, inactive_service):
        """Test that inactive services are not shown."""
        url = reverse("core:home")
        response = client.get(url)
        
        assert inactive_service.name not in response.content.decode()
```

### Testing Authentication

```python
def test_admin_required(client):
    """Test that admin panel requires authentication."""
    url = reverse("admin:index")
    response = client.get(url)
    
    # Should redirect to login
    assert response.status_code == 302
    assert "/login/" in response.url

def test_admin_access(admin_client):
    """Test admin access with authenticated client."""
    url = reverse("admin:core_service_changelist")
    response = admin_client.get(url)
    
    assert response.status_code == 200
```

## Testing Models

### Model Validation Tests

```python
def test_service_unique_name(db):
    """Test that service names must be unique."""
    from django.db import IntegrityError
    from apps.core.models import Service
    
    Service.objects.create(name="Duplicate")
    
    with pytest.raises(IntegrityError):
        Service.objects.create(name="Duplicate")

def test_service_ordering(db):
    """Test that services are ordered correctly."""
    from apps.core.models import Service
    
    service3 = Service.objects.create(name="Charlie", order=10)
    service1 = Service.objects.create(name="Alpha", order=0)
    service2 = Service.objects.create(name="Bravo", order=0)
    
    services = list(Service.objects.all())
    assert services == [service1, service2, service3]
```

### Model Method Tests

```python
def test_service_str_method(service):
    """Test the string representation of a service."""
    assert str(service) == service.name

def test_service_get_absolute_url(service):
    """Test service URL generation."""
    # If you add this method to the model
    assert service.get_absolute_url() == service.url
```

## Testing Forms

If you add forms to the project:

```python
def test_service_form_valid_data():
    """Test form with valid data."""
    from apps.core.forms import ServiceForm
    
    form = ServiceForm(data={
        'name': 'New Service',
        'description': 'A new service',
        'url': 'https://example.com',
        'icon': 'fas fa-plus',
        'is_active': True,
        'order': 10
    })
    
    assert form.is_valid()

def test_service_form_missing_name():
    """Test form requires name."""
    from apps.core.forms import ServiceForm
    
    form = ServiceForm(data={
        'description': 'Missing name'
    })
    
    assert not form.is_valid()
    assert 'name' in form.errors
```

## Test Coverage

### Running Coverage

```bash
# Run tests with coverage
just coverage

# View coverage report
open htmlcov/index.html
```

### Coverage Configuration

Set in `pyproject.toml`:
```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/migrations/*",
    "*/tests/*",
    "*/__init__.py",
    "src/config/settings/*",
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

### Coverage Goals

Aim for:
- 80%+ overall coverage
- 100% coverage for critical business logic
- Focus on testing behavior, not implementation

## Advanced Testing

### Parametrized Tests

```python
@pytest.mark.parametrize("name,valid", [
    ("Valid Name", True),
    ("", False),
    ("A" * 101, False),  # Too long
])
def test_service_name_validation(db, name, valid):
    """Test service name validation."""
    from apps.core.models import Service
    
    if valid:
        service = Service.objects.create(name=name)
        assert service.pk is not None
    else:
        with pytest.raises(Exception):
            Service.objects.create(name=name)
```

### Testing URLs

```python
def test_url_patterns():
    """Test URL configuration."""
    from django.urls import reverse, resolve
    
    # Test reverse
    url = reverse('core:home')
    assert url == '/'
    
    # Test resolve
    resolver = resolve('/')
    assert resolver.view_name == 'core:home'
```

### Mocking External Services

```python
from unittest.mock import patch

@patch('requests.get')
def test_service_health_check(mock_get, service):
    """Test checking service health."""
    mock_get.return_value.status_code = 200
    
    # Your health check code here
    is_healthy = check_service_health(service)
    
    assert is_healthy is True
    mock_get.assert_called_once_with(service.url)
```

## Test Best Practices

1. **Test Behavior, Not Implementation**: Focus on what the code does, not how

2. **Use Descriptive Names**: Test names should explain what they test

3. **Keep Tests Simple**: Each test should verify one thing

4. **Use Fixtures**: Don't repeat test data setup

5. **Test Edge Cases**: Empty lists, None values, invalid input

6. **Fast Tests**: Use in-memory database, avoid network calls

7. **Independent Tests**: Tests shouldn't depend on each other

## Debugging Tests

### Running Tests with Debugging

```bash
# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Show print statements
pytest -s

# Verbose output
pytest -vv
```

### Common Test Issues

**Database not available**
```python
# Always use pytest.mark.django_db
@pytest.mark.django_db
def test_needs_database():
    # Test code
```

**Import errors**
```python
# Ensure proper imports in conftest.py
import sys
from pathlib import Path

src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))
```

**Fixture not found**
```python
# Check fixture is in conftest.py or same file
# Check fixture name matches exactly
```

## Continuous Integration

`.github/workflows/ci.yml` runs on every push, pull request and manual dispatch.
It mirrors the local recipes: `just lint` (the pre-commit Ruff hooks over all
files), `ruff check` and `ruff format --check` on `src tests database_tests` with the locked
Ruff, and `just test` (`uv run pytest`), plus the dedicated database lanes below. Actions are pinned by commit SHA, the
token is read-only and no secrets are used. Development dependencies live in
the `dev` group under `[dependency-groups]`, which `uv sync` installs by default.


### Required Django gates

CI also runs these commands with the frozen dependencies and isolated test
settings (in-memory SQLite, no production secrets or external services):

```bash
UV_FROZEN=1 DJANGO_SETTINGS_MODULE=config.settings.test uv run python manage.py check
UV_FROZEN=1 DJANGO_SETTINGS_MODULE=config.settings.test uv run python manage.py makemigrations --check --dry-run
```

Both must pass alongside lint, format and tests. The first rejects invalid
Django configuration; the second rejects model changes without committed
migrations and writes no migration files. Test settings leave migration modules
enabled for management commands; pytest's `--no-migrations` option still bypasses
migrations when constructing its test database. `tests/test_ci_gates.py` verifies
the current source passes and intentional model/URL faults fail in disposable
source copies. Production `check --deploy` is a separate operator check.

### Media descriptor and routed admin logo regressions

`uv run pytest tests/core/test_media.py` uses synthetic files and deterministic
path replacements to check descriptor containment, regular-file identity,
streaming after replacement, internal links and conditional/header behavior.
Injected root-resolution failures must return 404 before any media file is opened;
a subsequent request with the restored root must stream normally.
Injected file-wrapper failures after a successful raw open must close every acquired
descriptor exactly once, including across repeated requests. Ownership transfers
first to `FileIO`, then to `BufferedReader`; failed buffer construction closes the
owning file object even if the buffer already closed it. Normal responses retain
their source until closed. Tests record open/close ownership directly, without
platform-specific descriptor enumeration.
It does not inspect platform-specific descriptor paths or use timing races.

`uv run pytest tests/core/test_add_default_services.py` also interleaves a real
owner save during synthetic logo copying. It checks that owner fields and a
competing logo survive, revisions advance only on attachment, and unused seed
allocations are removed. This deterministic seam covers the stale-read window
without relying on database-specific thread scheduling.
After compensation, a reused name must survive a later seed failure: ownership
ends at deletion, so rollback must not attempt that name a second time.

`uv run pytest tests/core/test_admin_conflicts.py` submits two valid quick edits,
saves the first row, then triggers a real unique-constraint database failure on
the second save. The test checks that all row fields/revisions roll back, real
logo retirement callbacks do not run, and a retry saves each row and runs each
callback once. Its counterfactual disables both changelist transaction scopes
(the custom validation scope and Django's built-in save scope): the first row
then persists and the rollback assertion fails. Removing only the custom scope
still leaves Django's save transaction protecting the writes; the contention
lane separately covers the validation lock lifetime.

The separate two-database runtime lane uses the existing file-backed settings:

```bash
UV_FROZEN=1 uv run python -m pytest database_tests/test_admin_logo_databases.py --ds=database_tests.settings --create-db
```

The equivalent recipe is `just test-admin-logos`. This is a local-only gate,
separate from ordinary pytest discovery and the existing Actions workflow.

A router sends Service reads/writes to `secondary`, while users/admin records
remain on `default`. Conflicting default rows and shared synthetic storage names
exercise replacement, clearing, individual/bulk deletion, delayed commit cleanup,
rollback, retained references, partial/failed uploads and post-commit compensation.
Default rows must remain unchanged. This tests existing alias behavior; it does
not introduce a new runtime routing policy. To check sensitivity, temporarily
route retirement reference checks, on-commit registration or failed-upload
reference checks to `default`: the corresponding tests must fail.

### Locked Python dependency audit

CI's separate, ten-minute audit job exports the frozen runtime graph and all
development groups (currently `dev`, including docs and pre-commit tooling).
Run the identical commands locally from the repository root:

```bash
uv export --frozen --all-groups --no-hashes --no-emit-project --output-file requirements-audit.txt
uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -r requirements-audit.txt
```

Run the second command only if the export succeeds. CI uses separate steps so
an export error stops the job; advisory findings and auditor/network errors
also fail it. The project itself is omitted because it is not a registry
package. `--no-deps` audits the already resolved export without installing or
resolving its packages. Requirements markers are evaluated for the audit
interpreter/platform (CI: Python 3.13 on Linux); this is not an audit of every
possible platform. The tool's own isolated environment and separately installed
pre-commit hook environments are outside the exported graph. A clean result
means no known advisories reported for the audited graph, not proof that every
usage is safe.


### Real database lanes

These required CI steps run separately from the fast model-sync suite:

```bash
UV_FROZEN=1 uv run pytest database_tests/test_admin_contention.py --create-db
UV_FROZEN=1 uv run pytest database_tests/test_applied_migrations.py --migrations --create-db
UV_FROZEN=1 uv run python -m pytest database_tests/test_seed_migrations.py --ds=database_tests.settings --migrations --create-db
```

The equivalent recipes are `just test-contention`, `just test-migrations`, and
`just test-seed-migrations`.
`database_tests/conftest.py` supplies a fresh temporary file-backed SQLite database
for each invocation. All lanes use only synthetic services/users and temporary
logo storage, with no production database or host access. They are outside the
ordinary `tests/` discovery path and never skip for a platform check.

The contention lane overlaps real admin POSTs on independent thread connections,
holding the winner at its conditional UPDATE until the second request attempts
its transaction. It requires a saved winner, a visible loser conflict, no mixed
fields or orphan logos, and no partially saved quick-edit batch. Removing the
validation transaction or SQLite's `IMMEDIATE` mode breaks this protection.

The applied-migration lane overrides pytest's default `--no-migrations` and
`--reuse-db`, executes every committed operation on a fresh database, checks the
recorded core leaves and Service columns, and round-trips a synthetic service.
The ordinary CI-gate tests inject a failing RunPython operation in a disposable
source copy: the drift check stays green but this lane must fail.


The seed lane uses `database_tests.settings` with two independent temporary SQLite
aliases. For every historical seed, MigrationExecutor runs forward and backward
on the secondary alias: exact default-database sentinels must stay unchanged,
owner-customized rows must retain all fields and primary keys, and newly inserted
rows must remain on reversal. The historical Open WebUI update is also checked
for connection-local writes. `python -m pytest` makes the test-only settings
package importable without changing application paths. Run this command separately
from the other lanes so each starts with its own fresh test databases.
