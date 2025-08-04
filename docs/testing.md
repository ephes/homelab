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

Example GitHub Actions workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install uv
        uv sync
    
    - name: Run tests
      run: |
        uv run pytest --cov
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```