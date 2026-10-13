import logging

from django.contrib import admin
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import router, transaction

from .models import Service

logger = logging.getLogger("homelab")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "is_active", "order", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["order", "name"]
    list_editable = ["order", "is_active"]
    fields = ["name", "description", "url", "icon", "logo_file", "is_active", "order"]

    def _retire_logos(self, names, using):
        storage = self.model._meta.get_field("logo_file").storage

        def cleanup():
            for name in set(names) - {""}:
                try:
                    if not self.model.objects.using(using).filter(logo_file=name).exists():
                        storage.delete(name)
                except Exception:
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
                logger.exception("Could not clean up failed service upload %s", name)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # ModelAdmin owns the atomic block inside this public entry point.
        # Catch outside it so even failures after save_model have rolled back.
        request._service_logo_uploads = []
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except BaseException:
            self._remove_failed_uploads(request._service_logo_uploads, using=router.db_for_write(self.model))
            raise
        finally:
            del request._service_logo_uploads

    def save_model(self, request, obj, form, change):
        using = router.db_for_write(self.model, instance=obj)
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
                    for chunk in upload.chunks():
                        destination.write(chunk)
                obj.logo_file = name
            super().save_model(request, obj, form, change)
        except BaseException:
            self._remove_failed_uploads(allocated)
            raise
        if hasattr(request, "_service_logo_uploads"):
            request._service_logo_uploads.extend(allocated)
        if old_name and old_name != obj.logo_file.name:
            self._retire_logos([old_name], using)

    def delete_model(self, request, obj):
        using = router.db_for_write(self.model, instance=obj)
        name = obj.logo_file.name
        super().delete_model(request, obj)
        self._retire_logos([name], using)

    def delete_queryset(self, request, queryset):
        using = queryset.db
        names = list(queryset.values_list("logo_file", flat=True))
        super().delete_queryset(request, queryset)
        self._retire_logos(names, using)
