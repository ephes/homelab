from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection

from apps.core.management.commands import inventory_service_logos


@pytest.fixture
def logo_directory(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    directory = tmp_path / "services" / "logos"
    directory.mkdir(parents=True)
    (directory / "partial.svg").write_bytes(b"<svg")
    return directory


def test_inventory_refuses_to_report_when_scan_limit_is_exceeded(logo_directory, monkeypatch):
    (logo_directory / "second.svg").touch()
    monkeypatch.setattr(inventory_service_logos, "MAX_ENTRIES", 1)
    output = StringIO()

    with pytest.raises(CommandError, match="inventory incomplete: more than 1 storage entries"):
        call_command("inventory_service_logos", stdout=output)

    assert output.getvalue() == ""


def test_inventory_refuses_to_report_when_storage_is_unreadable(logo_directory):
    # A non-directory at the configured storage prefix causes a real scan error.
    (logo_directory / "partial.svg").unlink()
    logo_directory.rmdir()
    logo_directory.touch()
    output = StringIO()

    with pytest.raises(CommandError, match="inventory incomplete"):
        call_command("inventory_service_logos", stdout=output)

    assert output.getvalue() == ""


def test_inventory_refuses_to_report_when_reference_lookup_fails(db, logo_directory, monkeypatch):
    (logo_directory / "second.svg").touch()
    monkeypatch.setattr(inventory_service_logos, "REFERENCE_BATCH_SIZE", 1)
    lookups = []
    output = StringIO()

    def fail_second_lookup(execute, sql, params, many, context):
        if sql.startswith("SELECT DISTINCT"):
            lookups.append(params)
            if len(lookups) == 2:
                raise DatabaseError("reference lookup failed")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_second_lookup), pytest.raises(CommandError, match="reference lookup failed"):
        call_command("inventory_service_logos", stdout=output)

    assert len(lookups) == 2
    assert output.getvalue() == ""
