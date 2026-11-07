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
