"""Deletion confirms the displayed service revision before audit/storage effects."""

import pytest
from django.contrib.admin.models import LogEntry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.models import Service

pytestmark = pytest.mark.django_db(transaction=True)


def single_confirmation(client, service):
    url = reverse("admin:core_service_delete", args=[service.pk])
    response = client.get(url)
    assert response.status_code == 200
    token = response.context.get("service_delete_confirmation", "")
    if token:
        assert f'name="service_delete_confirmation" value="{token}"' in response.content.decode()
    return url, token


def test_single_delete_preserves_newer_service_logo_and_audit(admin_client):
    service = Service.objects.create(name="Synthetic", url="https://old.example/")
    url, token = single_confirmation(admin_client, service)
    service.url = "https://new.example/"
    service.logo_file = SimpleUploadedFile("new.svg", b"new logo")
    service.save()
    before = Service.objects.values().get(pk=service.pk)
    logs = LogEntry.objects.count()
    response = admin_client.post(url, {"post": "yes", "service_delete_confirmation": token}, follow=True)
    assert Service.objects.filter(pk=service.pk).exists()
    assert Service.objects.values().get(pk=service.pk) == before
    assert service.logo_file.storage.exists(service.logo_file.name)
    assert LogEntry.objects.count() == logs
    assert b"Reload" in response.content

    url, token = single_confirmation(admin_client, service)
    assert token
    assert admin_client.post(url, {"post": "yes", "service_delete_confirmation": token}).status_code == 302
    assert not Service.objects.filter(pk=service.pk).exists()
    assert not service.logo_file.storage.exists(service.logo_file.name)
    assert LogEntry.objects.count() == logs + 1


@pytest.mark.parametrize("invalid", ["missing", "tampered", "oversize", "other_object"])
def test_single_delete_rejects_invalid_confirmation(admin_client, invalid):
    service = Service.objects.create(name="Synthetic")
    url, token = single_confirmation(admin_client, service)
    if invalid == "missing":
        token = ""
    elif invalid == "tampered":
        token += "x"
    elif invalid == "oversize":
        token = "x" * (128 * 1024 + 1)
    else:
        other = Service.objects.create(name="Other")
        _, token = single_confirmation(admin_client, other)
    logs = LogEntry.objects.count()
    response = admin_client.post(url, {"post": "yes", "service_delete_confirmation": token})
    assert response.status_code == 302
    assert Service.objects.filter(pk=service.pk).exists()
    assert LogEntry.objects.count() == logs


def test_single_confirmation_expires_and_is_bound_to_user(admin_client, django_user_model, monkeypatch):
    from django.core import signing

    service = Service.objects.create(name="Synthetic")
    url, token = single_confirmation(admin_client, service)
    now = signing.time.time()
    with monkeypatch.context() as patch:
        patch.setattr(signing.time, "time", lambda: now + 3601)
        admin_client.post(url, {"post": "yes", "service_delete_confirmation": token})
    assert Service.objects.filter(pk=service.pk).exists()
    other = django_user_model.objects.create_superuser(username="other", password="synthetic")
    admin_client.force_login(other)
    admin_client.post(url, {"post": "yes", "service_delete_confirmation": token})
    assert Service.objects.filter(pk=service.pk).exists()
    assert not LogEntry.objects.exists()


def bulk_confirmation(client, services, **extra):
    url = reverse("admin:core_service_changelist")
    data = {"action": "delete_selected", "_selected_action": [service.pk for service in services], **extra}
    response = client.post(url, data)
    assert response.status_code == 200
    token = response.context.get("service_delete_confirmation", "")
    if token:
        assert f'name="service_delete_confirmation" value="{token}"' in response.content.decode()
    data.pop("select_across", None)
    data.update(post="yes", service_delete_confirmation=response.context.get("service_delete_confirmation", ""))
    return url, data


@pytest.mark.parametrize(
    "change", ["edit", "disappear", "omit", "add", "unknown", "duplicate", "tamper", "missing", "oversize", "across"]
)
def test_bulk_delete_refuses_entire_changed_selection(admin_client, change):
    services = [
        Service.objects.create(name=name, logo_file=SimpleUploadedFile(f"{name}.svg", b"logo"))
        for name in ["First", "Second"]
    ]
    url, data = bulk_confirmation(admin_client, services)
    if change == "edit":
        services[1].url = "https://new.example/"
        services[1].logo_file = SimpleUploadedFile("replacement.svg", b"new logo")
        services[1].save()
    elif change == "disappear":
        Service.objects.filter(pk=services[1].pk).delete()
    elif change == "omit":
        data["_selected_action"] = [services[0].pk]
    elif change == "add":
        other = Service.objects.create(name="Unconfirmed")
        data["_selected_action"].append(other.pk)
    elif change == "unknown":
        data["_selected_action"].append(999999)
    elif change == "duplicate":
        data["_selected_action"].append(services[0].pk)
    elif change == "oversize":
        data["service_delete_confirmation"] = "x" * (128 * 1024 + 1)
    elif change == "tamper":
        data["service_delete_confirmation"] += "x"
    elif change == "missing":
        del data["service_delete_confirmation"]
    else:
        data["select_across"] = "1"
    before = list(Service.objects.order_by("pk").values())
    logs = LogEntry.objects.count()
    response = admin_client.post(url, data, follow=True)
    assert list(Service.objects.order_by("pk").values()) == before
    assert LogEntry.objects.count() == logs
    assert all(service.logo_file.storage.exists(service.logo_file.name) for service in services)
    assert b"Reload" in response.content


def test_fresh_bulk_confirmation_deletes_exact_displayed_rows(admin_client):
    services = [Service.objects.create(name=name) for name in ["First", "Second"]]
    url, data = bulk_confirmation(admin_client, services, select_across="1")
    token = data["service_delete_confirmation"]
    assert token
    later = Service.objects.create(name="Created after confirmation")
    assert admin_client.post(url, data).status_code == 302
    assert list(Service.objects.values_list("pk", flat=True)) == [later.pk]
    assert LogEntry.objects.count() == 2


@pytest.mark.parametrize("count", [500, 501])
def test_bulk_confirmation_selection_budget(admin_client, count):
    services = Service.objects.bulk_create([Service(name=f"Synthetic {i}") for i in range(count)])
    response = admin_client.post(
        reverse("admin:core_service_changelist"),
        {"action": "delete_selected", "_selected_action": [service.pk for service in services]},
    )
    assert Service.objects.count() == count
    assert not LogEntry.objects.exists()
    if count == 500:
        assert response.status_code == 200
        assert len(response.context["queryset"]) == count
        assert response.context["service_delete_confirmation"]
        data = {
            "action": "delete_selected",
            "_selected_action": [service.pk for service in services],
            "post": "yes",
            "service_delete_confirmation": response.context["service_delete_confirmation"],
        }
        assert admin_client.post(reverse("admin:core_service_changelist"), data).status_code == 302
        assert not Service.objects.exists()
        assert LogEntry.objects.count() == count
    else:
        assert response.status_code == 302


def test_confirmation_cannot_cross_single_and_bulk_journeys(admin_client):
    service = Service.objects.create(name="Synthetic")
    single_url, token = single_confirmation(admin_client, service)
    bulk_url, data = bulk_confirmation(admin_client, [service])
    admin_client.post(single_url, {"post": "yes", "service_delete_confirmation": data["service_delete_confirmation"]})
    data["service_delete_confirmation"] = token
    admin_client.post(bulk_url, data)
    assert Service.objects.filter(pk=service.pk).exists()
    assert not LogEntry.objects.exists()
