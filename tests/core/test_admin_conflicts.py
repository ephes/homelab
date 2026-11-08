"""Stale admin submissions retain newer rows and never allocate uploads."""

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.models import Service

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("logo_action", ["replace", "clear"])
def test_stale_change_form_retains_submission_and_newer_row(admin_client, tmp_path, settings, logo_action):
    settings.MEDIA_ROOT = str(tmp_path)
    service = Service.objects.create(name="Synthetic", url="https://old.example/", order=1)
    url = reverse("admin:core_service_change", args=[service.pk])
    first = admin_client.get(url)
    second = admin_client.get(url)
    data = {
        "name": service.name,
        "url": "https://new.example/",
        "order": "2",
        "original_revision": second.context["adminform"].form.initial["original_revision"],
        "logo_file": SimpleUploadedFile("current.svg", b"current"),
        "_save": "Save",
    }
    assert admin_client.post(url, data).status_code == 302
    service.refresh_from_db()
    before = Service.objects.values().get(pk=service.pk)
    data.update(
        url="https://submitted.example/",
        order="3",
        is_active="on",
        original_revision=first.context["adminform"].form.initial["original_revision"],
    )
    if logo_action == "replace":
        data["logo_file"] = SimpleUploadedFile("stale.svg", b"stale")
    else:
        del data["logo_file"]
        data["logo_file-clear"] = "on"
    response = admin_client.post(url, data)
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert "changed since" in str(form.non_field_errors())
    assert form["url"].value() == "https://submitted.example/"
    assert Service.objects.values().get(pk=service.pk) == before
    assert [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()] == [service.logo_file.name]
    assert service.logo_file.read() == b"current"

    # Reloading explicitly gives a revision which can be saved.
    fresh = admin_client.get(url).context["adminform"].form
    data["original_revision"] = fresh.initial["original_revision"]
    data.pop("logo_file", None)
    data.pop("logo_file-clear", None)
    assert admin_client.post(url, data).status_code == 302
    service.refresh_from_db()
    assert service.url == "https://submitted.example/"


def test_stale_list_edit_is_a_form_error_and_preserves_entire_batch(admin_client):
    services = [Service.objects.create(name=name, order=i) for i, name in enumerate(["First", "Second"])]
    url = reverse("admin:core_service_changelist")
    response = admin_client.get(url)
    assert 'name="form-0-original_revision"' in response.content.decode()
    forms = response.context["cl"].formset.forms
    data = {"form-TOTAL_FORMS": "2", "form-INITIAL_FORMS": "2", "_save": "Save"}
    for i, form in enumerate(forms):
        data.update(
            {
                f"form-{i}-id": str(form.instance.pk),
                f"form-{i}-order": str(10 + i),
                f"form-{i}-is_active": "on",
                f"form-{i}-original_revision": form.initial["original_revision"],
            }
        )
    services[1].order = 99
    services[1].save()
    before = list(Service.objects.order_by("pk").values())
    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert "changed since" in str(response.context["cl"].formset.non_form_errors()) + str(
        response.context["cl"].formset.errors
    )
    assert list(Service.objects.order_by("pk").values()) == before
    fresh_forms = admin_client.get(url).context["cl"].formset.forms
    for i, form in enumerate(fresh_forms):
        data[f"form-{i}-id"] = str(form.instance.pk)
        data[f"form-{i}-original_revision"] = form.initial["original_revision"]
    assert admin_client.post(url, data).status_code == 302
    assert list(Service.objects.order_by("order").values_list("order", flat=True)) == [10, 11]


def test_missing_revision_cannot_overwrite_service(admin_client, service):
    response = admin_client.post(
        reverse("admin:core_service_change", args=[service.pk]),
        {"name": service.name, "order": "99", "_save": "Save"},
    )
    assert response.status_code == 200
    service.refresh_from_db()
    assert service.order == 1


def test_list_edit_database_failure_rolls_back_saved_rows_and_callbacks(admin_client, tmp_path, settings, monkeypatch):
    from django.contrib import admin
    from django.db import IntegrityError, transaction

    settings.MEDIA_ROOT = tmp_path
    services = [
        Service.objects.create(name=name, order=i, is_active=False) for i, name in enumerate(["First", "Second"])
    ]
    url = reverse("admin:core_service_changelist")
    forms = admin_client.get(url).context["cl"].formset.forms
    data = {"form-TOTAL_FORMS": "2", "form-INITIAL_FORMS": "2", "_save": "Save"}
    expected_orders = {}
    for i, form in enumerate(forms):
        expected_orders[form.instance.pk] = 10 + i
        data.update(
            {
                f"form-{i}-id": str(form.instance.pk),
                f"form-{i}-order": str(10 + i),
                f"form-{i}-is_active": "on",
                f"form-{i}-original_revision": form.initial["original_revision"],
            }
        )
    before = list(Service.objects.order_by("pk").values())
    storage = Service._meta.get_field("logo_file").storage
    retired = {
        service.pk: storage.save(f"retired-{service.pk}.svg", ContentFile(b"synthetic old logo"))
        for service in services
    }
    original_save = Service.save
    attempted, saved, callbacks = [], [], []
    inject_failure = True

    def save_with_second_row_failure(self, *args, **kwargs):
        if self.pk not in expected_orders:
            return original_save(self, *args, **kwargs)
        attempted.append(self.pk)
        if inject_failure and len(attempted) == 2:
            # Raise a real unique-constraint database error after the first row
            # has been saved, rather than refusing the forms during validation.
            original_save(Service(name=services[0].name), force_insert=True)
            pytest.fail("the duplicate insert must fail")
        result = original_save(self, *args, **kwargs)
        current = Service.objects.get(pk=self.pk)
        assert current.order == expected_orders[self.pk]
        assert current.is_active
        assert current.updated_at != next(row["updated_at"] for row in before if row["id"] == self.pk)
        saved.append(self.pk)
        transaction.on_commit(lambda pk=self.pk: callbacks.append(pk), using=self._state.db)
        # Exercise the real cleanup callback without changing list-editable fields.
        admin.site._registry[Service]._retire_logos([retired[self.pk]], using=self._state.db)
        return result

    monkeypatch.setattr(Service, "save", save_with_second_row_failure)
    with pytest.raises(IntegrityError):
        admin_client.post(url, data)

    assert attempted == [form.instance.pk for form in forms]
    assert saved == attempted[:1]
    assert list(Service.objects.order_by("pk").values()) == before
    assert callbacks == []
    assert all(storage.exists(name) for name in retired.values())

    inject_failure = False
    attempted.clear()
    saved.clear()
    assert admin_client.post(url, data).status_code == 302
    assert saved == attempted == [form.instance.pk for form in forms]
    assert callbacks == saved
    assert dict(Service.objects.values_list("pk", "order")) == expected_orders
    assert not any(storage.exists(name) for name in retired.values())
