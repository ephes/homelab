"""The one supported dotenv file is ``<project root>/.env``."""

import pytest

from .isolation import load_settings, make_project_root, run_python, settings_module_bootstrap

ROOT_DOTENV = """\
DJANGO_SECRET_KEY=synthetic-root-dotenv-key
DATABASE_URL=sqlite:////synthetic/root-dotenv.sqlite3
DJANGO_ALLOWED_HOSTS=root-dotenv.invalid
"""


@pytest.fixture
def project_root(tmp_path):
    return make_project_root(tmp_path)


@pytest.mark.parametrize("settings_module", ["config.settings.local", "config.settings.production"])
def test_root_dotenv_is_read(project_root, settings_module):
    (project_root / ".env").write_text(ROOT_DOTENV)

    settings = load_settings(project_root, settings_module_bootstrap(settings_module))

    assert settings["SECRET_KEY"] == "synthetic-root-dotenv-key"
    assert settings["DATABASES"]["default"]["NAME"] == "/synthetic/root-dotenv.sqlite3"
    if settings_module == "config.settings.production":
        assert settings["ALLOWED_HOSTS"] == ["root-dotenv.invalid"]


def test_exported_environment_wins_over_root_dotenv(project_root):
    (project_root / ".env").write_text(ROOT_DOTENV)
    exported = {
        "DJANGO_SECRET_KEY": "synthetic-exported-key",
        "DATABASE_URL": "sqlite:////synthetic/exported.sqlite3",
    }

    settings = load_settings(project_root, settings_module_bootstrap("config.settings.production"), exported)

    assert settings["SECRET_KEY"] == "synthetic-exported-key"
    assert settings["DATABASES"]["default"]["NAME"] == "/synthetic/exported.sqlite3"
    # a variable that is only in the file still comes from the file
    assert settings["ALLOWED_HOSTS"] == ["root-dotenv.invalid"]


def test_src_dotenv_is_not_read_and_is_reported(project_root):
    (project_root / "src" / ".env").write_text("DJANGO_SECRET_KEY=synthetic-src-dotenv-key\n")

    result = run_python(
        project_root,
        settings_module_bootstrap("config.settings.local")
        + "from django.conf import settings\nprint('KEY', settings.SECRET_KEY)\n",
    )

    assert result.returncode == 0, result.stderr
    assert "synthetic-src-dotenv-key" not in result.stdout
    assert "KEY django-insecure-CHANGEME-IN-PRODUCTION" in result.stdout
    assert "RuntimeWarning" in result.stderr
    assert f"{project_root / 'src' / '.env'} is not read" in result.stderr
    # the warning names the file, never its contents
    assert "synthetic-src-dotenv-key" not in result.stderr


def test_production_requires_a_secret_key_without_dotenv(project_root):
    result = run_python(
        project_root,
        settings_module_bootstrap("config.settings.production") + "from django.conf import settings\nsettings.DEBUG\n",
    )

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr
