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
