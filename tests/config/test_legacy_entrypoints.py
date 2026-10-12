"""``homelab.wsgi`` / ``homelab.asgi`` must never start the retired development settings."""

import pytest

from .isolation import load_settings, make_project_root, run_python

LEGACY_FIXED_SECRET_PREFIX = "django-insecure-h#5by"
SYNTHETIC_ENV = {"DJANGO_SECRET_KEY": "synthetic-entrypoint-key"}


@pytest.fixture
def project_root(tmp_path):
    return make_project_root(tmp_path)


def entrypoint_bootstrap(module: str) -> str:
    # The project root is the working directory, as for a WSGI/ASGI server
    # started there. PYTHONPATH (src) alone does not expose ``homelab``.
    return f"import sys\nsys.path.insert(0, '')\nimport {module}\nassert callable({module}.application)\n"


@pytest.mark.parametrize("module", ["homelab.wsgi", "homelab.asgi", "config.wsgi"])
def test_entrypoint_without_settings_variable_selects_production(project_root, module):
    settings = load_settings(project_root, entrypoint_bootstrap(module), SYNTHETIC_ENV)

    assert settings["SETTINGS_MODULE"] == "config.settings.production"
    assert settings["DEBUG"] is False
    assert settings["SECRET_KEY"] == "synthetic-entrypoint-key"
    assert not settings["SECRET_KEY"].startswith(LEGACY_FIXED_SECRET_PREFIX)
    assert settings["ROOT_URLCONF"] == "config.urls"
    assert "apps.core" in settings["INSTALLED_APPS"]


@pytest.mark.parametrize("module", ["homelab.wsgi", "homelab.asgi"])
def test_legacy_entrypoint_fails_without_secret_instead_of_using_a_fixed_one(project_root, module):
    result = run_python(project_root, entrypoint_bootstrap(module))

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


@pytest.mark.parametrize("module", ["homelab.wsgi", "homelab.asgi", "config.wsgi"])
def test_entrypoint_keeps_explicit_settings_module(project_root, module):
    env = {"DJANGO_SETTINGS_MODULE": "config.settings.test"}

    settings = load_settings(project_root, entrypoint_bootstrap(module), env)

    assert settings["SETTINGS_MODULE"] == "config.settings.test"
    assert settings["DEBUG"] is False
    assert settings["DATABASES"]["default"]["NAME"] == ":memory:"


@pytest.mark.parametrize("module", ["homelab.wsgi", "homelab.asgi"])
def test_retired_settings_module_cannot_be_selected(project_root, module):
    env = {"DJANGO_SETTINGS_MODULE": "homelab.settings", **SYNTHETIC_ENV}

    result = run_python(project_root, entrypoint_bootstrap(module), env)

    assert result.returncode != 0
    assert "homelab.settings is retired" in result.stderr
    assert "config.settings.production" in result.stderr
