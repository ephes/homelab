"""Logo retirement through real admin requests and database commits."""

from contextlib import nullcontext

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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
            data = {"name": service.name, "order": "0", "is_active": "on", "_save": "Save"}
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
