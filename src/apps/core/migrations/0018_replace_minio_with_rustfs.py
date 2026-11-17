"""Replace the retired MinIO tile with RustFS, the S3 store in use since 2026-11-17.

Narrowly guarded: only a tile named ``MinIO`` that still links to the retired
MinIO console is changed. Its description and icon are replaced only while they
are the old seed values, and its logo reference is cleared only while it names a
seeded ``minio*.png`` copy (``add_default_services`` then fills the RustFS logo).
Active status and order stay as the owner set them. If a ``RustFS`` tile already
exists, the retired MinIO tile is only hidden. The stored MinIO logo file is not
deleted. The reverse keeps the replacement (MinIO no longer exists).
"""

import re

from django.db import migrations

MINIO_URL = "https://minio.home.xn--wersdrfer-47a.de/"
MINIO_DESCRIPTION = "S3-compatible object storage for backups and data archiving"
MINIO_ICON = "fas fa-database"
SEEDED_MINIO_LOGO = re.compile(r"services/logos/minio(_[A-Za-z0-9]+)?\.png")

# Kept equal to the RustFS entry of add_default_services (tested).
RUSTFS = {
    "name": "RustFS",
    "description": (
        "S3-compatible object storage (RustFS on Fractal) for backups and application data. "
        "S3 API at https://s3.home.xn--wersdrfer-47a.de/ (LAN and Tailnet, signed requests only, no web console)"
    ),
    "url": "",
    "icon": "fas fa-database",
}


def replace_minio_with_rustfs(apps, schema_editor):
    Service = apps.get_model("core", "Service")
    services = Service.objects.using(schema_editor.connection.alias)
    minio = services.filter(name="MinIO", url=MINIO_URL).first()
    if minio is None:
        return
    if services.filter(name=RUSTFS["name"]).exists():
        minio.is_active = False
        minio.save(update_fields=["is_active", "updated_at"])
        return
    minio.name = RUSTFS["name"]
    minio.url = RUSTFS["url"]
    if minio.description == MINIO_DESCRIPTION:
        minio.description = RUSTFS["description"]
    if minio.icon == MINIO_ICON:
        minio.icon = RUSTFS["icon"]
    if SEEDED_MINIO_LOGO.fullmatch(minio.logo_file.name or ""):
        minio.logo_file = ""
    minio.save()


def keep_replacement(apps, schema_editor):
    """MinIO is retired: the reverse does not bring its tile back."""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_merge_20260505_1239"),
    ]

    operations = [
        migrations.RunPython(replace_minio_with_rustfs, keep_replacement),
    ]
