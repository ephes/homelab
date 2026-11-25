import logging
from contextlib import suppress

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected as django_delete_selected
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import router, transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.urls import reverse

from .logo_storage import write_logo_chunk
from .models import Service

logger = logging.getLogger("homelab")
MAX_LOGO_BYTES = 1024 * 1024
MAX_DELETE_SERVICES = 500
MAX_DELETE_CONFIRMATION_BYTES = 128 * 1024
DELETE_CONFIRMATION_SALT = "core.service.delete.v1"


class DeleteConfirmationConflict(Exception):
    pass


LOGO_SIZE_ERROR = "Logo files must be at most 1 MiB (1,048,576 bytes)."


class ServiceAdminForm(forms.ModelForm):
    original_revision = forms.DateTimeField(widget=forms.HiddenInput, required=False)
    write_database: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance._state.adding:
            self.initial["original_revision"] = self.instance.updated_at.isoformat()

    def clean_logo_file(self):
        upload = self.cleaned_data.get("logo_file")
        if not isinstance(upload, UploadedFile):
            return upload
        expected_size = upload.size
        if expected_size > MAX_LOGO_BYTES:
            raise forms.ValidationError(LOGO_SIZE_ERROR)
        # Validate actual bytes before storage allocation, and keep a bounded
        # snapshot so saving cannot replay a different/untrusted upload stream.
        content = bytearray()
        for chunk in upload.chunks():
            if len(chunk) > MAX_LOGO_BYTES - len(content):
                raise forms.ValidationError(LOGO_SIZE_ERROR)
            content.extend(chunk)
        if len(content) != expected_size:
            raise forms.ValidationError("The uploaded logo does not match its declared size.")
        return UploadedFile(
            file=ContentFile(content), name=upload.name, content_type=upload.content_type, size=expected_size
        )

    def clean(self):
        cleaned = super().clean()
        if not self.instance._state.adding and not self.errors:
            using = self.write_database or router.db_for_write(Service, instance=self.instance)
            revision = cleaned.get("original_revision")
            # Both admin entry points keep validation and save in one atomic
            # block. A conditional no-op UPDATE checks the revision and takes a
            # write lock (including SQLite) until that block ends, before uploads.
            if revision is None or not Service.objects.using(using).filter(
                pk=self.instance.pk, updated_at=revision
            ).update(updated_at=F("updated_at")):
                raise forms.ValidationError(
                    "This service changed since you opened the form. Reload it and reapply your changes."
                )
        return cleaned

    def validate_unique(self):
        if self.write_database is None:
            return super().validate_unique()
        # Service.name is the only unique field (guarded by a model test).
        # Django's model validation uses the read router for field uniqueness,
        # even on a loaded instance.
        if "name" in self.cleaned_data:
            duplicates = Service.objects.using(self.write_database).filter(name=self.instance.name)
            if not self.instance._state.adding:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                error = self.instance.unique_error_message(Service, ["name"])
                self.add_error("name", error)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    form = ServiceAdminForm
    actions = ["delete_selected"]
    delete_selected_confirmation_template = "admin/core/service/delete_selected_confirmation.html"
    delete_confirmation_template = "admin/core/service/delete_confirmation.html"
    change_list_template = "admin/core/service/change_list.html"
    list_display = ["name", "url", "is_active", "order", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["order", "name"]
    list_editable = ["order", "is_active"]
    fields = ["name", "description", "url", "icon", "logo_file", "is_active", "order", "original_revision"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if hasattr(request, "_service_delete_using"):
            return queryset.using(request._service_delete_using)
        if hasattr(request, "_service_change_using"):
            return queryset.using(request._service_change_using)
        if hasattr(request, "_service_list_edit_using"):
            return queryset.using(request._service_list_edit_using)
        return queryset

    def _delete_payload(self, request, objects, using, mode):
        return {
            "mode": mode,
            "database": using,
            "user": str(request.user.pk),
            "rows": [[str(obj.pk), obj.updated_at.isoformat()] for obj in objects],
        }

    def _sign_delete_confirmation(self, request, objects, using, mode):
        return signing.dumps(self._delete_payload(request, objects, using, mode), salt=DELETE_CONFIRMATION_SALT)

    def _claim_delete_confirmation(self, request, objects, using, mode):
        tokens = request.POST.getlist("service_delete_confirmation")
        if len(tokens) != 1 or len(tokens[0]) > MAX_DELETE_CONFIRMATION_BYTES or not tokens[0].isascii():
            raise DeleteConfirmationConflict
        try:
            payload = signing.loads(tokens[0], salt=DELETE_CONFIRMATION_SALT, max_age=3600)
        except (signing.BadSignature, ValueError, TypeError):
            raise DeleteConfirmationConflict from None
        if payload != self._delete_payload(request, objects, using, mode):
            raise DeleteConfirmationConflict
        for obj in objects:
            # Claim each displayed revision before audit/deletion/storage effects.
            # A no-op UPDATE also locks SQLite writers until transaction exit.
            if (
                not self.model.objects.using(using)
                .filter(pk=obj.pk, updated_at=obj.updated_at)
                .update(updated_at=F("updated_at"))
            ):
                raise DeleteConfirmationConflict

    def _delete_conflict(self, request):
        self.message_user(
            request,
            "Deletion confirmation changed, expired or is invalid. "
            "Reload and confirm the current services again (at most 500).",
            messages.ERROR,
        )
        return HttpResponseRedirect(reverse("admin:core_service_changelist", current_app=self.admin_site.name))

    def delete_view(self, request, object_id, extra_context=None):
        using = router.db_for_write(self.model)
        request._service_delete_using = using
        try:
            response = super().delete_view(request, object_id, extra_context)
            if request.method in {"GET", "HEAD"} and hasattr(response, "context_data"):
                obj = response.context_data["object"]
                response.context_data["service_delete_confirmation"] = self._sign_delete_confirmation(
                    request, [obj], using, "single"
                )
            return response
        except DeleteConfirmationConflict:
            return self._delete_conflict(request)
        finally:
            del request._service_delete_using

    def log_deletions(self, request, queryset):
        if hasattr(request, "_service_delete_using"):
            self._claim_delete_confirmation(request, list(queryset), request._service_delete_using, "single")
        return super().log_deletions(request, queryset)

    @admin.action(permissions=["delete"], description="Delete selected %(verbose_name_plural)s")
    def delete_selected(self, request, queryset):
        using = router.db_for_write(self.model)
        try:
            with transaction.atomic(using=using):
                queryset = queryset.using(using).order_by("pk")
                # Cache one bounded snapshot for both the displayed objects and
                # their signature, including the 'select all' journey.
                displayed = queryset[: MAX_DELETE_SERVICES + 1]
                objects = list(displayed)
                if len(objects) > MAX_DELETE_SERVICES:
                    raise DeleteConfirmationConflict
                if request.POST.get("post"):
                    selected = request.POST.getlist(ACTION_CHECKBOX_NAME)
                    ids = {str(obj.pk) for obj in objects}
                    if (
                        request.POST.get("select_across") not in {None, "0"}
                        or len(selected) != len(ids)
                        or set(selected) != ids
                    ):
                        raise DeleteConfirmationConflict
                    self._claim_delete_confirmation(request, objects, using, "bulk")
                    # Freeze membership even if the original filter would match
                    # newly created services after the confirmation was shown.
                    return django_delete_selected(self, request, queryset.filter(pk__in=ids))
                response = django_delete_selected(self, request, displayed)
                response.context_data["service_delete_confirmation"] = self._sign_delete_confirmation(
                    request, objects, using, "bulk"
                )
                return response
        except DeleteConfirmationConflict:
            return self._delete_conflict(request)

    def get_changelist_form(self, request, **kwargs):
        form = super().get_changelist_form(request, form=ServiceAdminForm, **kwargs)
        form.write_database = getattr(request, "_service_list_edit_using", None)
        return form

    def changelist_view(self, request, extra_context=None):
        # Django otherwise validates list-editable forms before its save block.
        if request.method != "POST" or "_save" not in request.POST:
            return super().changelist_view(request, extra_context)
        using = router.db_for_write(self.model)
        request._service_list_edit_using = using
        try:
            with transaction.atomic(using=using):
                return super().changelist_view(request, extra_context)
        finally:
            del request._service_list_edit_using

    def _retire_logos(self, names, using):
        names = set(names) - {""}
        if not names:
            return
        storage = self.model._meta.get_field("logo_file").storage

        def cleanup():
            logos = self.model.objects.using(using)
            try:
                # The bulk action bounds this lookup to MAX_DELETE_SERVICES.
                referenced = set(
                    logos.filter(logo_file__in=names).order_by().values_list("logo_file", flat=True).distinct()
                )
            except Exception:
                # A failed batch must still check ownership for each file.
                referenced = None
                with suppress(Exception):
                    logger.exception("Could not check references for retired service logos in bulk")
            for name in names:
                try:
                    still_used = logos.filter(logo_file=name).exists() if referenced is None else name in referenced
                    if not still_used:
                        storage.delete(name)
                except Exception:
                    with suppress(Exception):
                        logger.exception("Could not clean up retired service logo %s", name)

        transaction.on_commit(cleanup, using=using, robust=True)

    def _remove_failed_uploads(self, names, using=None):
        storage = self.model._meta.get_field("logo_file").storage
        for name in names:
            try:
                # A non-robust on_commit callback can raise after a successful
                # commit. Never compensate an upload the database retained.
                if using is None or not self.model.objects.using(using).filter(logo_file=name).exists():
                    storage.delete(name)
            except Exception:
                # Keep the save error and check the remaining allocations.
                with suppress(Exception):
                    logger.exception("Could not clean up failed service upload %s", name)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        form.write_database = getattr(request, "_service_change_using", None)
        return form

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # ModelAdmin owns the atomic block inside this public entry point.
        # Catch outside it so even failures after save_model have rolled back.
        if request.method == "POST":
            # Match Django's model-level transaction route for adds and edits.
            request._service_change_using = router.db_for_write(self.model)
        request._service_logo_uploads = []
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except BaseException:
            for name, using in request._service_logo_uploads:
                self._remove_failed_uploads([name], using=using)
            raise
        finally:
            del request._service_logo_uploads
            if hasattr(request, "_service_change_using"):
                del request._service_change_using

    def save_model(self, request, obj, form, change):
        pinned_using = getattr(request, "_service_change_using", None) or getattr(
            request, "_service_list_edit_using", None
        )
        using = pinned_using or router.db_for_write(self.model, instance=obj)
        old_name = ""
        if change:
            old_name = self.model.objects.using(using).get(pk=obj.pk).logo_file.name
        allocated = []
        try:
            upload = form.cleaned_data.get("logo_file")
            if isinstance(upload, UploadedFile):
                field = self.model._meta.get_field("logo_file")
                storage = field.storage
                # Reserve an exclusively owned name before copying any bytes,
                # as add_default_services does, so partial writes are tracked.
                name = storage.save(
                    field.generate_filename(obj, upload.name), ContentFile(b""), max_length=field.max_length
                )
                allocated.append(name)
                with storage.open(name, "wb") as destination:
                    written = 0
                    for chunk in upload.chunks():
                        written += len(chunk)
                        if written > MAX_LOGO_BYTES:
                            raise forms.ValidationError(LOGO_SIZE_ERROR)
                        write_logo_chunk(destination, chunk)
                obj.logo_file = name
            if pinned_using is None:
                super().save_model(request, obj, form, change)
            else:
                obj.save(using=using)
        except BaseException:
            # Inside a transaction on the write alias the row change rolls back
            # with this error. Without a transaction on that alias,
            # Model.save can commit before a post_save receiver raises. Keep
            # any file the committed row references.
            in_transaction = transaction.get_connection(using).in_atomic_block
            self._remove_failed_uploads(allocated, using=None if in_transaction else using)
            raise
        if hasattr(request, "_service_logo_uploads"):
            request._service_logo_uploads.extend((name, using) for name in allocated)
        if old_name and old_name != obj.logo_file.name:
            self._retire_logos([old_name], using)

    def delete_model(self, request, obj):
        using = getattr(request, "_service_delete_using", None) or router.db_for_write(self.model, instance=obj)
        name = obj.logo_file.name
        obj.delete(using=using)
        self._retire_logos([name], using)

    def delete_queryset(self, request, queryset):
        using = queryset.db
        names = list(queryset.values_list("logo_file", flat=True))
        super().delete_queryset(request, queryset)
        self._retire_logos(names, using)
