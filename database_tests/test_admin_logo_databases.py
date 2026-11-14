"""Admin logo ownership follows the routed write database, never default rows."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models.signals import post_save
from django.urls import reverse

from apps.core.models import Service

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
            response = admin_client.post(reverse("admin:core_service_delete", args=[service.pk]), {"post": "yes"})
        else:
            response = admin_client.post(
                reverse("admin:core_service_changelist"),
                {"action": "delete_selected", "_selected_action": [service.pk], "post": "yes"},
            )
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


@pytest.mark.parametrize("failure", ["row", "related", "write"])
@pytest.mark.parametrize("change", [True, False])
def test_secondary_failed_upload_removes_only_owned_allocation(
    admin_client, settings, tmp_path, monkeypatch, failure, change
):
    settings.MEDIA_ROOT = tmp_path
    service = Service.objects.create(name="Secondary", logo_file=SimpleUploadedFile("same.svg", b"old logo"))
    old_name, storage = service.logo_file.name, service.logo_file.storage
    Service.objects.create(name="Retained secondary reference", logo_file=old_name)
    Service.objects.using("default").create(pk=service.pk, name="Default sentinel", logo_file=old_name)
    before = default_rows()
    reached = []

    def fail(*args, **kwargs):
        reached.append(True)
        raise RuntimeError("injected failure")

    if failure == "related":
        monkeypatch.setattr(admin.site._registry[Service], "save_related", fail)
    elif failure == "write":
        original_open = storage.open

        @contextmanager
        def failing_open(name, mode="rb"):
            with original_open(name, mode) as destination:
                if mode == "wb":
                    original_write = destination.write

                    def partial_write(chunk):
                        original_write(chunk[:3])
                        fail()

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
        with pytest.raises(RuntimeError, match="injected failure"):
            admin_client.post(url, data)
    finally:
        post_save.disconnect(fail, sender=Service)
    assert reached
    service.refresh_from_db()
    assert service.logo_file.name == old_name
    assert Service.objects.count() == 2
    assert default_rows() == before
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()) == [old_name]
    with storage.open(old_name, "rb") as source:
        assert source.read() == b"old logo"


def test_secondary_post_commit_error_keeps_referenced_upload(admin_client, monkeypatch):
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
    service = Service.objects.get(name="Committed secondary")
    with service.logo_file.open("rb") as source:
        assert source.read() == b"new logo"
    assert default_rows() == before
