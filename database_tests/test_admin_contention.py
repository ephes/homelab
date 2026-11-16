"""Overlapping HTTP submissions must keep the validation lock through saving."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

from apps.core.models import Service

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("entrypoint", ["changeform", "changelist"])
def test_overlapping_admin_saves_preserve_winner_and_entire_losing_batch(admin_client, isolated_media_root, entrypoint):
    assert connection.vendor == "sqlite"
    assert "memory" not in str(connection.settings_dict["NAME"])
    services = [Service.objects.create(name=name, order=i) for i, name in enumerate(["First", "Second"])]
    user_pk = get_user_model().objects.get(username="admin").pk
    first_locked, release_first, second_started = Event(), Event(), Event()
    second_entered = Event()
    clients = [Client(raise_request_exception=False), Client(raise_request_exception=False)]
    for client in clients:
        client.force_login(get_user_model().objects.get(pk=user_pk))
    if entrypoint == "changeform":
        url = reverse("admin:core_service_change", args=[services[1].pk])
        revision = admin_client.get(url).context["adminform"].form.initial["original_revision"]

        def payload(label):
            return {
                "name": "Second",
                "url": f"https://{label}.example/",
                "order": "10" if label == "winner" else "20",
                "original_revision": revision,
                "logo_file": SimpleUploadedFile(f"{label}.svg", label.encode()),
                "_save": "Save",
            }
    else:
        url = reverse("admin:core_service_changelist")
        forms = admin_client.get(url).context["cl"].formset.forms

        def payload(label):
            selected = forms[1:] if label == "winner" else forms
            data = {"form-TOTAL_FORMS": str(len(selected)), "form-INITIAL_FORMS": str(len(selected)), "_save": "Save"}
            for i, form in enumerate(selected):
                data.update(
                    {
                        f"form-{i}-id": str(form.instance.pk),
                        f"form-{i}-order": "10" if label == "winner" else "20",
                        f"form-{i}-original_revision": form.initial["original_revision"],
                        f"form-{i}-is_active": "on",
                    }
                )
            return data

    def submit(index, label):
        def at_write(execute, sql, params, many, context):
            if index == 1 and sql.startswith("BEGIN"):
                second_started.set()
            result = execute(sql, params, many, context)
            if index == 1 and sql.startswith("BEGIN"):
                second_entered.set()
            if index == 0 and sql.startswith('UPDATE "core_service" SET "updated_at" ='):
                first_locked.set()
                assert release_first.wait(10), "first request was never released"
            return result

        try:
            with connection.execute_wrapper(at_write):
                response = clients[index].post(url, payload(label))
                return response.status_code, response.content.decode()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit, 0, "winner")
        try:
            assert first_locked.wait(10), "winner never reached conditional UPDATE"
            second = pool.submit(submit, 1, "loser")
            assert second_started.wait(10), "losing request never attempted its transaction"
            assert not second_entered.wait(0.2), "loser entered while the winner should hold the write lock"
            assert not second.done(), "loser finished before the winner released the lock"
        finally:
            release_first.set()
        assert first.result(timeout=15)[0] == 302
        code, body = second.result(timeout=15)
    assert code == 200
    assert "changed since" in body
    services[0].refresh_from_db()
    services[1].refresh_from_db()
    assert services[0].order == 0  # No partial batch save.
    assert services[1].order == 10
    if entrypoint == "changeform":
        assert services[1].url == "https://winner.example/"
        assert services[1].logo_file.read() == b"winner"
        assert [
            p.relative_to(isolated_media_root).as_posix() for p in isolated_media_root.rglob("*") if p.is_file()
        ] == [services[1].logo_file.name]


@pytest.mark.parametrize("mode", ["single", "bulk"])
def test_deletion_waits_for_edit_and_rejects_stale_confirmation(admin_client, mode):
    from django.contrib.admin.models import LogEntry

    from tests.core.test_admin_deletion import bulk_confirmation, single_confirmation

    services = [Service.objects.create(name=name) for name in ["First", "Second"]]
    service = services[1]
    if mode == "single":
        delete_url, token = single_confirmation(admin_client, service)
        delete_data = {"post": "yes", "service_delete_confirmation": token}
    else:
        delete_url, delete_data = bulk_confirmation(admin_client, services)
    change_url = reverse("admin:core_service_change", args=[service.pk])
    revision = admin_client.get(change_url).context["adminform"].form.initial["original_revision"]
    edit_data = {
        "name": service.name,
        "url": "https://winner.example/",
        "order": "9",
        "original_revision": revision,
        "logo_file": SimpleUploadedFile("winner.svg", b"winner"),
        "_save": "Save",
    }
    clients = [Client(raise_request_exception=False), Client(raise_request_exception=False)]
    for client in clients:
        client.force_login(get_user_model().objects.get(username="admin"))
    locked, release, attempted, entered = Event(), Event(), Event(), Event()

    def submit(index, url, data):
        def at_write(execute, sql, params, many, context):
            if index == 1 and sql.startswith("BEGIN"):
                attempted.set()
            result = execute(sql, params, many, context)
            if index == 1 and sql.startswith("BEGIN"):
                entered.set()
            if index == 0 and sql.startswith('UPDATE "core_service" SET "updated_at" ='):
                locked.set()
                assert release.wait(10)
            return result

        try:
            with connection.execute_wrapper(at_write):
                return clients[index].post(url, data).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(submit, 0, change_url, edit_data)
        try:
            assert locked.wait(10)
            deletion = pool.submit(submit, 1, delete_url, delete_data)
            assert attempted.wait(10)
            assert not entered.wait(0.2)
            assert not deletion.done()
        finally:
            release.set()
        assert winner.result(timeout=15) == 302
        assert deletion.result(timeout=15) == 302
    service.refresh_from_db()
    assert service.url == "https://winner.example/"
    assert service.order == 9
    assert service.logo_file.read() == b"winner"
    assert Service.objects.count() == 2
    assert not LogEntry.objects.filter(action_flag=3).exists()
