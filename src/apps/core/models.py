from django.db import models


class Service(models.Model):
    """Represents a service or application in the homelab."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order (lower numbers appear first)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.name
