import logging

from django.contrib import admin
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

    def save_model(self, request, obj, form, change):
        using = router.db_for_write(self.model, instance=obj)
        old_name = ""
        if change:
            old_name = self.model.objects.using(using).get(pk=obj.pk).logo_file.name
        super().save_model(request, obj, form, change)
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
