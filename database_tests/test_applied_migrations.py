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
