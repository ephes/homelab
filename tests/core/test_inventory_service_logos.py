from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection

from apps.core.management.commands import inventory_service_logos
from apps.core.models import Service


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


def test_inventory_refuses_to_report_when_reference_lookup_fails(db, logo_directory):
    (logo_directory / "second.svg").touch()
    lookups = []
    output = StringIO()

    def fail_lookup(execute, sql, params, many, context):
        if sql.startswith("SELECT DISTINCT"):
            lookups.append(params)
            raise DatabaseError("reference lookup failed")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_lookup), pytest.raises(CommandError, match="reference lookup failed"):
        call_command("inventory_service_logos", stdout=output)

    assert len(lookups) == 1
    assert output.getvalue() == ""


def test_inventory_reads_all_references_in_one_query(db, logo_directory):
    # More files than any reasonable IN-list batch, still one reference query.
    for name in ["first.svg", "second.svg", "third.svg", *(f"extra-{index:03}.svg" for index in range(600))]:
        (logo_directory / name).touch()
    Service.objects.create(name="First", logo_file="services/logos/first.svg")
    Service.objects.create(name="Third", logo_file="services/logos/third.svg")
    Service.objects.create(name="Without logo")
    lookups = []
    output = StringIO()

    def record_lookup(execute, sql, params, many, context):
        if "core_service" in sql:
            lookups.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record_lookup):
        call_command("inventory_service_logos", stdout=output)

    # A single statement sees one database snapshot on every backend.
    assert len(lookups) == 1
    lines = output.getvalue().splitlines()
    reported = [line.split(" age_seconds=")[0] for line in lines[:-1]]
    assert '"services/logos/first.svg"' not in reported
    assert '"services/logos/third.svg"' not in reported
    assert reported[-2:] == ['"services/logos/partial.svg"', '"services/logos/second.svg"']
    assert lines[-1] == "602 of 604 service logo files unreferenced on default."
