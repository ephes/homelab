"""Database lanes use a real temporary SQLite file, never an operator database."""

import pytest
from django.conf import settings

from tests.conftest import admin_client, isolated_media_root  # noqa: F401


@pytest.fixture(scope="session")
def django_db_modify_db_settings(tmp_path_factory):
    settings.DATABASES["default"]["TEST"]["NAME"] = str(tmp_path_factory.mktemp("database") / "default.sqlite3")
