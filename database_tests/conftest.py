"""Database lanes use real temporary SQLite files, never operator databases."""

import pytest
from django.conf import settings

from tests.conftest import admin_client, isolated_media_root  # noqa: F401


@pytest.fixture(scope="session")
def django_db_modify_db_settings(tmp_path_factory):
    root = tmp_path_factory.mktemp("database")
    for alias, database in settings.DATABASES.items():
        database["TEST"]["NAME"] = str(root / f"{alias}.sqlite3")
