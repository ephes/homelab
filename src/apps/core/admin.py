from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "is_active", "order", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["order", "name"]
    list_editable = ["order", "is_active"]
    fields = ["name", "description", "url", "icon", "logo_file", "is_active", "order"]
