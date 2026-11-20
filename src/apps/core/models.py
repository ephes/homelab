from django.db import models


class Service(models.Model):
    """Represents a service or application in the homelab."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class (fallback if no logo)")
    logo_file = models.FileField(upload_to="services/logos/", blank=True, help_text="Custom logo file (SVG, PNG, etc.)")
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order (lower numbers appear first)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        indexes = [models.Index(fields=["logo_file"], name="core_service_logo_file_idx")]
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.name


class LoginThrottleBucket(models.Model):
    """Failed-login budget for one hashed key (username + client address, or client address)."""

    key = models.CharField(max_length=100, unique=True)
    failures = models.PositiveIntegerField(default=0)
    # db_default keeps inserts that omit the column working, so code without
    # this field (workers still running during a deploy, or a rollback) can
    # still record failures after migration 0020.
    charge_sequence = models.PositiveBigIntegerField(default=0, db_default=0)
    expires_at = models.FloatField(help_text="Unix time at which this window ends")

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]

    def __str__(self):
        return self.key
