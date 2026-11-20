"""The separate --migrations lane executes the graph on a fresh database."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from apps.core.models import Service


@pytest.mark.django_db(transaction=True)
def test_applied_leaf_and_service_schema(django_db_use_migrations):
    assert django_db_use_migrations, "Run this lane with --migrations --create-db"
    leaves = MigrationExecutor(connection).loader.graph.leaf_nodes("core")
    assert leaves
    assert set(leaves) <= set(MigrationRecorder(connection).applied_migrations())
    with connection.cursor() as cursor:
        columns = {column.name for column in connection.introspection.get_table_description(cursor, "core_service")}
    assert columns == {field.column for field in Service._meta.local_fields}
    service = Service.objects.create(name="Migration probe", url="https://synthetic.example/", order=42)
    loaded = Service.objects.get(pk=service.pk)
    assert (loaded.name, loaded.url, loaded.order, loaded.is_active, loaded.logo_file.name) == (
        "Migration probe",
        "https://synthetic.example/",
        42,
        True,
        "",
    )


@pytest.mark.django_db(transaction=True)
def test_logo_index_supports_exact_and_bulk_reference_checks(django_db_use_migrations):
    assert django_db_use_migrations, "Run this lane with --migrations --create-db"
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes("core")
    previous = [("core", "0020_login_throttle_charge_sequence")]
    shared = "services/logos/shared.svg"
    case_variant = "services/logos/Shared.svg"
    unused = "services/logos/unused.svg"
    services = Service.objects.order_by()
    exact = services.filter(logo_file=shared)
    single = exact.values("pk")[:1]
    bulk = services.filter(logo_file__in={shared, unused}).values_list("logo_file", flat=True).distinct()

    try:
        executor.migrate(previous)
        Service.objects.bulk_create(
            [Service(name=f"Indexed probe {i}", logo_file=f"services/logos/probe-{i}.svg") for i in range(1000)]
            + [
                Service(name="Shared owner 1", logo_file=shared),
                Service(name="Shared owner 2", logo_file=shared),
                Service(name="Case variant owner", logo_file=case_variant),
            ]
        )
        for lookup in (single, bulk):
            assert "SCAN core_service" in lookup.explain()
    finally:
        MigrationExecutor(connection).migrate(leaves)

    for lookup in (single, bulk):
        plan = lookup.explain()
        assert "SEARCH core_service" in plan and "core_service_logo_file_idx" in plan, plan

    assert set(exact.values_list("name", flat=True)) == {"Shared owner 1", "Shared owner 2"}
    assert set(bulk.iterator()) == {shared}
    exact.filter(name="Shared owner 1").delete()
    assert exact.exists()
    assert set(bulk.iterator()) == {shared}
    exact.delete()
    assert not exact.exists()
    assert not bulk.exists()
    assert services.filter(logo_file=case_variant).exists()
