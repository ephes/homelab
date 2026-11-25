"""Admin logo ownership follows the routed write database, never default rows."""

import os
from contextlib import contextmanager
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import transaction
from django.db.models.signals import post_save
from django.urls import reverse

from apps.core.management.commands import inventory_service_logos
from apps.core.models import Service
from tests.core.test_admin_deletion import bulk_confirmation, single_confirmation

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "secondary"])


class SecondaryServiceRouter:
    def db_for_read(self, model, **hints):
        return "secondary" if model is Service else None

    def db_for_write(self, model, **hints):
        return "secondary" if model is Service else None


@pytest.fixture(autouse=True)
def routed_services(settings):
    settings.DATABASE_ROUTERS = [SecondaryServiceRouter()]


def change_data(service):
    return {
        "name": service.name,
        "order": "0",
        "is_active": "on",
        "_save": "Save",
        "original_revision": service.updated_at.isoformat(),
    }


def default_rows():
    return list(Service.objects.using("default").order_by("pk").values())


def test_logo_inventory_finds_interrupted_allocation_on_writer(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    settings.DATABASE_ROUTERS = [SplitServiceRouter()]
    service = Service.objects.using("secondary").create(
        name="Writer logo", logo_file=SimpleUploadedFile("live.svg", b"<svg/>"), is_active=False
    )
    storage = service.logo_file.storage
    orphan = storage.save("services/logos/recovery/interrupted.svg", ContentFile(b""))
    untouched = storage.save("other/interrupted.svg", ContentFile(b""))
    os.utime(storage.path(orphan), (1_000, 1_000))
    monkeypatch.setattr(inventory_service_logos, "time", lambda: 1_123)
    Service.objects.using("default").create(name="Reader decoy", logo_file=orphan)
    output = StringIO()

    call_command("inventory_service_logos", stdout=output)

    assert output.getvalue().count("age_seconds=") == 1
    assert f'"{orphan}" age_seconds=123' in output.getvalue()
    assert service.logo_file.name not in output.getvalue()
    assert "1 of 2 service logo files unreferenced on secondary." in output.getvalue()
    assert storage.exists(orphan)
    assert storage.exists(untouched)
    assert storage.exists(service.logo_file.name)
    assert Service.objects.using("default").filter(logo_file=orphan).exists()


@pytest.mark.parametrize("action", ["replace", "clear", "delete", "bulk"])
@pytest.mark.parametrize("outcome", ["commit", "rollback", "shared", "late_reference", "default_reference"])
def test_retirement_uses_secondary_commit_and_references(admin_client, action, outcome):
    service = Service.objects.create(name="Secondary", logo_file=SimpleUploadedFile("old.svg", b"old logo"))
    assert service._state.db == "secondary"
    name, storage = service.logo_file.name, service.logo_file.storage
    decoy = Service.objects.using("default").create(
        pk=service.pk, name="Default sentinel", logo_file=name if outcome == "default_reference" else "default.svg"
    )
    if outcome == "shared":
        Service.objects.create(name="Retained secondary reference", logo_file=name)
    before = default_rows()

    with transaction.atomic(using="secondary"):
        if action in {"replace", "clear"}:
            data = change_data(service)
            if action == "replace":
                data["logo_file"] = SimpleUploadedFile("new.svg", b"new logo")
            else:
                data["logo_file-clear"] = "on"
            response = admin_client.post(reverse("admin:core_service_change", args=[service.pk]), data)
        elif action == "delete":
            url, token = single_confirmation(admin_client, service)
            response = admin_client.post(url, {"post": "yes", "service_delete_confirmation": token})
        else:
            url, data = bulk_confirmation(admin_client, [service])
            response = admin_client.post(url, data)
        assert response.status_code == 302
        # Default is in autocommit: registering there would run too early.
        assert storage.exists(name)
        if outcome == "late_reference":
            Service.objects.create(name="Reference before secondary commit", logo_file=name)
        if outcome == "rollback":
            transaction.set_rollback(True, using="secondary")

    assert storage.exists(name) == (outcome in {"rollback", "shared", "late_reference"})
    assert default_rows() == before
    assert Service.objects.using("default").get(pk=decoy.pk).name == "Default sentinel"
    if outcome == "rollback":
        service.refresh_from_db()
        assert service.logo_file.name == name
        with storage.open(name, "rb") as source:
            assert source.read() == b"old logo"
    elif action == "replace":
        service.refresh_from_db()
        with service.logo_file.open("rb") as source:
            assert source.read() == b"new logo"
    elif action == "clear":
        service.refresh_from_db()
        assert not service.logo_file
    else:
        assert not Service.objects.filter(pk=service.pk).exists()


@pytest.mark.parametrize("failure", ["row", "related", "write", "short_write"])
@pytest.mark.parametrize("change", [True, False])
def test_secondary_failed_upload_removes_only_owned_allocation(
    admin_client, settings, tmp_path, monkeypatch, failure, change
):
    settings.MEDIA_ROOT = tmp_path
    service = Service.objects.create(name="Secondary", logo_file=SimpleUploadedFile("same.svg", b"old logo"))
    old_name, storage = service.logo_file.name, service.logo_file.storage
    old_revision = service.updated_at
    Service.objects.create(name="Retained secondary reference", logo_file=old_name)
    Service.objects.using("default").create(pk=service.pk, name="Default sentinel", logo_file=old_name)
    before = default_rows()
    reached = []

    def fail(*args, **kwargs):
        reached.append(True)
        raise RuntimeError("injected failure")

    if failure == "related":
        monkeypatch.setattr(admin.site._registry[Service], "save_related", fail)
    elif failure in {"write", "short_write"}:
        original_open = storage.open

        @contextmanager
        def failing_open(name, mode="rb"):
            with original_open(name, mode) as destination:
                if mode == "wb":
                    original_write = destination.write

                    def partial_write(chunk):
                        count = original_write(chunk[:3])
                        if failure == "write":
                            fail()
                        reached.append(True)
                        return count

                    yield SimpleNamespace(write=partial_write)
                else:
                    yield destination

        monkeypatch.setattr(storage, "open", failing_open)
    else:
        post_save.connect(fail, sender=Service, weak=False)
    data = change_data(service)
    data.update(name="Secondary" if change else "New", logo_file=SimpleUploadedFile("same.svg", b"new logo"))
    url = reverse("admin:core_service_change", args=[service.pk]) if change else reverse("admin:core_service_add")
    try:
        expected_error = (
            pytest.raises(OSError, match="Short write")
            if failure == "short_write"
            else pytest.raises(RuntimeError, match="injected failure")
        )
        with expected_error:
            admin_client.post(url, data)
    finally:
        post_save.disconnect(fail, sender=Service)
    assert reached
    service.refresh_from_db()
    assert service.logo_file.name == old_name
    assert service.updated_at == old_revision
    assert Service.objects.count() == 2
    assert default_rows() == before
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()) == [old_name]
    with storage.open(old_name, "rb") as source:
        assert source.read() == b"old logo"


class SplitServiceRouter(SecondaryServiceRouter):
    def db_for_read(self, model, **hints):
        return "default" if model is Service else None

    def db_for_write(self, model, **hints):
        if model is Service:
            return "default" if hints.get("instance") is not None else "secondary"
        return None


@pytest.mark.parametrize("save_as_new", [False, True], ids=["add", "save-as-new"])
@pytest.mark.parametrize("case", ["writer-duplicate", "reader-duplicate", "rollback"])
def test_new_service_validates_and_saves_on_writer(admin_client, settings, tmp_path, case, save_as_new):
    settings.MEDIA_ROOT = tmp_path
    settings.DATABASE_ROUTERS = [SplitServiceRouter()]
    original = Service.objects.using("secondary").create(
        name="Original", logo_file=SimpleUploadedFile("original.svg", b"old logo")
    )
    old_logo = original.logo_file.name
    replica = Service.objects.using("default").create(pk=original.pk, name="Replica original")
    Service.objects.using("secondary").create(name="Writer-only name")
    Service.objects.using("default").create(name="Reader-only name")
    before = default_rows()
    data = change_data(replica)
    data["name"] = {
        "writer-duplicate": "Writer-only name",
        "reader-duplicate": "Reader-only name",
        "rollback": "New name",
    }[case]
    data["logo_file"] = SimpleUploadedFile("new.svg", b"new logo")
    if save_as_new:
        url = reverse("admin:core_service_change", args=[original.pk])
        data["_saveasnew"] = data.pop("_save")
    else:
        url = reverse("admin:core_service_add")

    writer = Service.objects.using("secondary")

    def fail(sender, instance, using, **kwargs):
        assert using == "secondary"
        assert transaction.get_connection(using).in_atomic_block
        raise RuntimeError("injected writer insert failure")

    if case == "rollback":
        post_save.connect(fail, sender=Service)
        try:
            with pytest.raises(RuntimeError, match="injected writer insert failure"):
                admin_client.post(url, data)
        finally:
            post_save.disconnect(fail, sender=Service)
        assert not writer.filter(name=data["name"]).exists()
    else:
        response = admin_client.post(url, data)
        if case == "writer-duplicate":
            assert response.status_code == 200
            assert response.context["adminform"].form.errors.as_data()["name"][0].code == "unique"
        else:
            assert response.status_code == 302
            created = writer.get(name=data["name"])
            assert created.pk != original.pk
            with created.logo_file.open("rb") as source:
                assert source.read() == b"new logo"

    assert default_rows() == before
    assert writer.get(pk=original.pk).updated_at == original.updated_at
    with original.logo_file.open("rb") as source:
        assert source.read() == b"old logo"
    assert writer.count() == (3 if case == "reader-duplicate" else 2)
    if case != "reader-duplicate":
        assert [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()] == [old_logo]


@pytest.mark.parametrize("instance_routing", [False, True])
def test_secondary_post_commit_error_keeps_referenced_upload(admin_client, monkeypatch, settings, instance_routing):
    if instance_routing:
        settings.DATABASE_ROUTERS = [SplitServiceRouter()]

    # No default row references this upload: compensation must query secondary.
    Service.objects.using("default").create(name="Default sentinel", logo_file="unrelated.svg")
    before = default_rows()
    model_admin = admin.site._registry[Service]
    save_related = model_admin.save_related
    reached = []

    def fail():
        reached.append(True)
        raise RuntimeError("after secondary commit")

    def schedule_failure(*args, **kwargs):
        save_related(*args, **kwargs)
        transaction.on_commit(fail, using="secondary")

    monkeypatch.setattr(model_admin, "save_related", schedule_failure)
    with pytest.raises(RuntimeError, match="after secondary commit"):
        admin_client.post(
            reverse("admin:core_service_add"),
            {
                "name": "Committed secondary",
                "order": "0",
                "is_active": "on",
                "_save": "Save",
                "logo_file": SimpleUploadedFile("new.svg", b"new logo"),
            },
        )
    assert reached
    service = Service.objects.using("secondary").get(name="Committed secondary")
    with service.logo_file.open("rb") as source:
        assert source.read() == b"new logo"
    assert default_rows() == before


def test_list_edit_selects_claims_and_saves_writer(admin_client, settings):
    settings.DATABASE_ROUTERS = [SplitServiceRouter()]
    service = Service.objects.using("secondary").create(name="Writer", order=1)
    replica = Service.objects.using("default").create(pk=service.pk, name="Stale replica", order=2)
    before = default_rows()
    url = reverse("admin:core_service_changelist")

    forms = admin_client.get(url).context["cl"].formset.forms
    assert [form.instance.name for form in forms] == [replica.name]

    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-0-id": str(service.pk),
        "form-0-order": "10",
        "form-0-is_active": "on",
        "form-0-original_revision": service.updated_at.isoformat(),
        "_save": "Save",
    }
    assert admin_client.post(url, data).status_code == 302
    service.refresh_from_db(using="secondary")
    assert (service.name, service.order) == ("Writer", 10)
    assert default_rows() == before

    data.update({"form-0-order": "20", "form-0-original_revision": replica.updated_at.isoformat()})
    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert "changed since" in str(response.context["cl"].formset.forms[0].non_field_errors())
    service.refresh_from_db(using="secondary")
    assert service.order == 10
    assert default_rows() == before


@pytest.mark.parametrize("case", ["save", "stale", "duplicate", "rollback"])
def test_single_edit_loads_validates_and_saves_on_writer(admin_client, settings, tmp_path, case):
    settings.MEDIA_ROOT = tmp_path
    settings.DATABASE_ROUTERS = [SplitServiceRouter()]
    service = Service.objects.using("secondary").create(
        name="Writer", logo_file=SimpleUploadedFile("old.svg", b"old logo")
    )
    replica = Service.objects.using("default").create(pk=service.pk, name="Replica")
    Service.objects.using("default").create(name="Replica-only name")
    Service.objects.using("secondary").create(name="Writer-only name")
    before = default_rows()
    original_revision = service.updated_at
    old_logo = service.logo_file.name
    storage = service.logo_file.storage
    url = reverse("admin:core_service_change", args=[service.pk])
    assert admin_client.get(url).context["adminform"].form.instance.name == replica.name

    data = change_data(service)
    data["name"] = "Writer-only name" if case == "duplicate" else "Replica-only name"
    data["logo_file"] = SimpleUploadedFile("new.svg", b"new logo")
    if case == "stale":
        data["name"] = "Stale edit"
        data["original_revision"] = replica.updated_at.isoformat()

    def fail(sender, instance, using, **kwargs):
        assert using == "secondary"
        assert transaction.get_connection(using).in_atomic_block
        raise RuntimeError("injected writer row failure")

    if case == "rollback":
        post_save.connect(fail, sender=Service)
        try:
            with pytest.raises(RuntimeError, match="injected writer row failure"):
                admin_client.post(url, data)
        finally:
            post_save.disconnect(fail, sender=Service)
    else:
        response = admin_client.post(url, data)
        if case == "save":
            assert response.status_code == 302
        else:
            assert response.status_code == 200
            form = response.context["adminform"].form
            assert form.initial["name"] == "Writer"
            if case == "stale":
                assert "changed since" in str(form.non_field_errors())
            else:
                assert form.errors.as_data()["name"][0].code == "unique"

    service.refresh_from_db(using="secondary")
    assert default_rows() == before
    if case == "save":
        assert service.name == "Replica-only name"
        assert service.updated_at > original_revision
        with service.logo_file.open("rb") as source:
            assert source.read() == b"new logo"
        assert not storage.exists(old_logo)
    else:
        assert service.name == "Writer"
        assert service.updated_at == original_revision
        assert service.logo_file.name == old_logo
        assert [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()] == [old_logo]


def test_single_confirmation_claims_deletes_and_retires_on_writer(admin_client, settings):
    settings.DATABASE_ROUTERS = [SplitServiceRouter()]
    writer = Service.objects.using("secondary")
    service = writer.create(name="Writer", logo_file=SimpleUploadedFile("writer.svg", b"writer logo"))
    replica = Service.objects.using("default").create(
        pk=service.pk, name="Reader sentinel", logo_file=SimpleUploadedFile("reader.svg", b"reader logo")
    )
    storage = service.logo_file.storage
    before = default_rows()

    url, token = single_confirmation(admin_client, service)
    service.name = "New writer generation"
    service.save(using="secondary")
    admin_client.post(url, {"post": "yes", "service_delete_confirmation": token})
    assert writer.filter(pk=service.pk).exists()
    assert default_rows() == before
    assert storage.exists(service.logo_file.name)

    url, token = single_confirmation(admin_client, service)
    with transaction.atomic(using="secondary"):
        assert admin_client.post(url, {"post": "yes", "service_delete_confirmation": token}).status_code == 302
        assert not writer.filter(pk=service.pk).exists()
        assert default_rows() == before
        assert storage.exists(service.logo_file.name)

    assert not storage.exists(service.logo_file.name)
    with replica.logo_file.open("rb") as source:
        assert source.read() == b"reader logo"


@pytest.mark.parametrize("change", ["edit", "disappear", "database"])
def test_bulk_confirmation_claims_one_writer_generation(admin_client, settings, change):
    from django.contrib.admin.models import LogEntry

    class SplitRouter(SecondaryServiceRouter):
        def db_for_read(self, model, **hints):
            return "default" if model is Service else None

    settings.DATABASE_ROUTERS = [SplitRouter()]
    services = [
        Service.objects.create(name=name, logo_file=SimpleUploadedFile(f"{name}.svg", b"logo"))
        for name in ["First", "Second"]
    ]
    for service in services:
        Service.objects.using("default").create(pk=service.pk, name=f"Sentinel {service.pk}")
    before_default = default_rows()
    url, data = bulk_confirmation(admin_client, services)
    if change == "edit":
        services[1].url = "https://writer.example/"
        services[1].save()
    elif change == "disappear":
        Service.objects.filter(pk=services[1].pk).delete()
    else:
        # Even identical row IDs/revisions on another alias cannot reuse a token.
        for service in services:
            Service.objects.using("default").filter(pk=service.pk).update(updated_at=service.updated_at)
        before_default = default_rows()
        settings.DATABASE_ROUTERS = []
    before = list(Service.objects.using("secondary").order_by("pk").values())
    logs = LogEntry.objects.count()
    assert admin_client.post(url, data).status_code == 302
    assert list(Service.objects.using("secondary").order_by("pk").values()) == before
    assert default_rows() == before_default
    assert LogEntry.objects.count() == logs
    assert all(service.logo_file.storage.exists(service.logo_file.name) for service in services)
    if change != "database":
        remaining = list(Service.objects.using("secondary").all())
        url, data = bulk_confirmation(admin_client, remaining)
        assert admin_client.post(url, data).status_code == 302
        assert not Service.objects.using("secondary").exists()
        assert default_rows() == before_default
