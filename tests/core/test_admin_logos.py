"""Logo retirement through real admin requests and database commits."""

from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.db import transaction
from django.urls import reverse

from apps.core.admin import logger
from apps.core.models import Service

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("action", ["replace", "clear", "delete", "bulk"])
@pytest.mark.parametrize("outcome", ["commit", "rollback", "shared", "late_reference"])
def test_admin_logo_retirement(admin_client, action, outcome):
    service = Service.objects.create(name="Logo service", logo_file=SimpleUploadedFile("old.svg", b"old logo"))
    name, storage = service.logo_file.name, service.logo_file.storage
    if outcome == "shared":
        Service.objects.create(name="Shared logo", logo_file=name)
    second_name = None
    if action == "bulk":
        second = Service.objects.create(name="Second", logo_file=SimpleUploadedFile("second.svg", b"second logo"))
        second_name = second.logo_file.name
        selected = [service.pk, second.pk]
        # Both selected rows can also share the same retired object.
        Service.objects.create(name="Selected shared", logo_file=name)
        selected.append(Service.objects.get(name="Selected shared").pk)

    with nullcontext() if outcome == "commit" else transaction.atomic():
        if action in {"replace", "clear"}:
            data = {
                "name": service.name,
                "order": "0",
                "is_active": "on",
                "_save": "Save",
                "original_revision": service.updated_at.isoformat(),
            }
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
                {"action": "delete_selected", "_selected_action": selected, "post": "yes"},
            )
        assert response.status_code == 302
        assert storage.exists(name) == (outcome != "commit")
        if second_name:
            assert storage.exists(second_name) == (outcome != "commit")
        if action == "replace":
            service.refresh_from_db()
            with service.logo_file.open("rb") as upload:
                assert upload.read() == b"new logo"
        if outcome == "late_reference":
            Service.objects.create(name="Reference before commit", logo_file=name)
        if outcome == "rollback":
            transaction.set_rollback(True)

    assert storage.exists(name) == (outcome != "commit")
    if second_name:
        assert storage.exists(second_name) == (outcome == "rollback")
    if outcome == "rollback":
        service.refresh_from_db()
        assert service.logo_file.name == name
    elif action == "replace":
        service.refresh_from_db()
        assert storage.exists(service.logo_file.name)
    elif action == "clear":
        service.refresh_from_db()
        assert not service.logo_file
    else:
        assert not Service.objects.filter(pk=service.pk).exists()


def test_bulk_cleanup_failure_is_logged_and_other_files_are_removed(admin_client, monkeypatch, caplog):
    services = [
        Service.objects.create(name=name, logo_file=SimpleUploadedFile(f"{name}.svg", b"logo"))
        for name in ["Broken", "Working"]
    ]
    storage = services[0].logo_file.storage
    names = {service.logo_file.name for service in services}
    failed = []
    monkeypatch.setattr(logger, "propagate", True)
    delete = storage.delete

    def failing_delete(name):
        if not failed:
            failed.append(name)
            raise OSError("Storage unavailable")
        delete(name)

    monkeypatch.setattr(storage, "delete", failing_delete)
    response = admin_client.post(
        reverse("admin:core_service_changelist"),
        {"action": "delete_selected", "_selected_action": [service.pk for service in services], "post": "yes"},
    )
    assert response.status_code == 302
    assert not Service.objects.exists()
    assert len(failed) == 1
    broken = failed[0]
    assert storage.exists(broken)
    assert all(not storage.exists(name) for name in names - {broken})
    assert broken in caplog.text
    assert "Storage unavailable" in caplog.text


@pytest.mark.parametrize("failure", ["row", "related", "write"])
@pytest.mark.parametrize("change", [True, False])
def test_failed_admin_upload_removes_only_new_file(admin_client, settings, tmp_path, monkeypatch, failure, change):
    from django.contrib import admin
    from django.db.models.signals import post_save

    settings.MEDIA_ROOT = str(tmp_path)
    service = Service.objects.create(name="Original", logo_file=SimpleUploadedFile("same.svg", b"old logo"))
    old_name = service.logo_file.name
    storage = service.logo_file.storage
    Service.objects.create(name="Shared", logo_file=old_name)
    model_admin = admin.site._registry[Service]
    reached = []

    def fail(*args, **kwargs):
        reached.append(True)
        raise RuntimeError("injected failure")

    if failure == "related":
        monkeypatch.setattr(model_admin, "save_related", fail)
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
    url = reverse("admin:core_service_change", args=[service.pk]) if change else reverse("admin:core_service_add")
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            admin_client.post(
                url,
                {
                    "name": "Original" if change else "New",
                    "original_revision": service.updated_at.isoformat(),
                    "order": "0",
                    "is_active": "on",
                    "logo_file": SimpleUploadedFile("same.svg", b"new logo"),
                    "_save": "Save",
                },
            )
    finally:
        post_save.disconnect(fail, sender=Service)
    assert reached
    service.refresh_from_db()
    assert service.logo_file.name == old_name
    assert Service.objects.count() == 2
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()) == [old_name]
    with storage.open(old_name, "rb") as source:
        assert source.read() == b"old logo"


def test_successful_admin_add_keeps_upload(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    response = admin_client.post(
        reverse("admin:core_service_add"),
        {
            "name": "Uploaded",
            "order": "0",
            "is_active": "on",
            "_save": "Save",
            "logo_file": SimpleUploadedFile("new.svg", b"new logo"),
        },
    )
    assert response.status_code == 302
    service = Service.objects.get(name="Uploaded")
    with service.logo_file.open("rb") as source:
        assert source.read() == b"new logo"


def test_post_commit_error_keeps_committed_upload(admin_client, settings, tmp_path, monkeypatch):
    from django.contrib import admin

    settings.MEDIA_ROOT = str(tmp_path)
    model_admin = admin.site._registry[Service]
    save_related = model_admin.save_related
    reached = []

    def fail():
        reached.append(True)
        raise RuntimeError("after commit")

    def schedule_failure(*args, **kwargs):
        save_related(*args, **kwargs)
        transaction.on_commit(fail)

    monkeypatch.setattr(model_admin, "save_related", schedule_failure)
    with pytest.raises(RuntimeError, match="after commit"):
        admin_client.post(
            reverse("admin:core_service_add"),
            {
                "name": "Committed",
                "order": "0",
                "is_active": "on",
                "_save": "Save",
                "logo_file": SimpleUploadedFile("new.svg", b"new logo"),
            },
        )
    assert reached
    service = Service.objects.get(name="Committed")
    with service.logo_file.open("rb") as source:
        assert source.read() == b"new logo"


@pytest.mark.parametrize("change", [False, True])
@pytest.mark.parametrize("kind", ["declared", "lying_single", "lying_late", "boundary"])
def test_admin_logo_byte_budget(admin_client, settings, tmp_path, monkeypatch, change, kind):
    limit = 1024 * 1024
    settings.MEDIA_ROOT = tmp_path
    service = Service.objects.create(name="Original", logo_file=SimpleUploadedFile("old.svg", b"old logo"))
    old_name, old_revision = service.logo_file.name, service.updated_at
    storage = service.logo_file.storage
    before = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()}
    writes = []
    original_open = storage.open

    def record_open(name, mode="rb"):
        if "w" in mode:
            writes.append(name)
        return original_open(name, mode)

    monkeypatch.setattr(storage, "open", record_open)
    chunks_seen = []
    if kind.startswith("lying"):

        def lying_chunks(self, chunk_size=None):
            if kind == "lying_late":
                chunks_seen.append("partial")
                yield b"x" * (limit - 1)
                yield b"xx"
            else:
                yield b"x" * (limit + 1)
            chunks_seen.append("past limit")
            pytest.fail("oversized input must not be consumed further")

        monkeypatch.setattr(InMemoryUploadedFile, "chunks", lying_chunks)
        payload = b"claimed small"
    else:
        payload = b"x" * (limit + (kind == "declared"))
        if kind == "declared":

            def unexpected_chunks(self, chunk_size=None):
                pytest.fail("declared oversize must be rejected before reading chunks")

            monkeypatch.setattr(InMemoryUploadedFile, "chunks", unexpected_chunks)
    url = reverse("admin:core_service_change", args=[service.pk]) if change else reverse("admin:core_service_add")
    response = admin_client.post(
        url,
        {
            "name": "Changed" if change else "New",
            "original_revision": old_revision.isoformat(),
            "order": "1",
            "is_active": "on",
            "_save": "Save",
            "logo_file": SimpleUploadedFile("new.svg", payload),
        },
    )
    service.refresh_from_db()
    if kind == "boundary":
        assert response.status_code == 302
        saved = service if change else Service.objects.get(name="New")
        with saved.logo_file.open("rb") as source:
            assert source.read() == payload
        assert writes
    else:
        assert response.status_code == 200
        assert "at most 1 MiB" in str(response.context["adminform"].form.errors["logo_file"])
        assert not writes
        assert service.name == "Original"
        assert service.updated_at == old_revision
        assert service.logo_file.name == old_name
        assert Service.objects.count() == 1
        assert {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()} == before
        with storage.open(old_name, "rb") as source:
            assert source.read() == b"old logo"
        assert "past limit" not in chunks_seen


def test_admin_logo_copy_enforces_budget_after_reservation(settings, tmp_path, monkeypatch):
    from django.contrib import admin
    from django.core.exceptions import ValidationError
    from django.test import RequestFactory

    settings.MEDIA_ROOT = tmp_path
    service = Service.objects.create(name="Original", logo_file=SimpleUploadedFile("old.svg", b"old logo"))
    old_name, old_revision = service.logo_file.name, service.updated_at
    storage = service.logo_file.storage
    upload = SimpleUploadedFile("new.svg", b"claimed small")
    writes = []
    original_open = storage.open

    class RecordingDestination:
        def __init__(self, source):
            self.source = source

        def __enter__(self):
            return self

        def write(self, chunk):
            writes.append(len(chunk))
            return self.source.write(chunk)

        def __exit__(self, *args):
            self.source.close()

    def record_open(name, mode="rb"):
        source = original_open(name, mode)
        return RecordingDestination(source) if mode == "wb" else source

    def chunks(chunk_size=None):
        yield b"x" * (1024 * 1024 - 1)
        yield b"xx"
        pytest.fail("must stop at the first excess chunk")

    monkeypatch.setattr(upload, "chunks", chunks)
    monkeypatch.setattr(storage, "open", record_open)
    service.logo_file = upload
    service.name = "Changed"
    with pytest.raises(ValidationError, match="at most 1 MiB"):
        admin.site._registry[Service].save_model(
            RequestFactory().post("/"), service, SimpleNamespace(cleaned_data={"logo_file": upload}), True
        )
    assert writes == [1024 * 1024 - 1]
    service.refresh_from_db()
    assert (service.name, service.logo_file.name, service.updated_at) == ("Original", old_name, old_revision)
    assert [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()] == [old_name]


@pytest.mark.parametrize("temporary", [False, True])
def test_admin_saves_only_the_validated_logo_snapshot(admin_client, settings, monkeypatch, temporary):
    from django.core.files.uploadedfile import TemporaryUploadedFile

    if temporary:
        settings.FILE_UPLOAD_MAX_MEMORY_SIZE = 0
    calls = []

    def changing_chunks(self, chunk_size=None):
        calls.append(self)
        assert len(calls) == 1, "saving must not replay the untrusted input"
        yield b"checked logo"

    monkeypatch.setattr(TemporaryUploadedFile if temporary else InMemoryUploadedFile, "chunks", changing_chunks)
    response = admin_client.post(
        reverse("admin:core_service_add"),
        {
            "name": "Snapshot",
            "order": "0",
            "is_active": "on",
            "_save": "Save",
            "logo_file": SimpleUploadedFile("new.svg", b"claimed small"),
        },
    )
    assert response.status_code == 302
    assert len(calls) == 1
    service = Service.objects.get(name="Snapshot")
    with service.logo_file.open("rb") as source:
        assert source.read() == b"checked logo"
