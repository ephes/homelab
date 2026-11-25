import json
import os
import stat
from pathlib import Path
from time import time

from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, router

from apps.core.models import Service

MAX_ENTRIES = 10_000


def _file_mtimes(root: Path, prefix: str) -> dict[str, float]:
    files = {}
    try:
        entries = os.scandir(root)
    except FileNotFoundError:
        # Before the first upload, the logo directory need not exist.
        return files

    pending = []
    scanned = 0
    while True:
        with entries:
            for entry in entries:
                scanned += 1
                if scanned > MAX_ENTRIES:
                    raise CommandError(f"Service logo inventory incomplete: more than {MAX_ENTRIES} storage entries")
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    pending.append(entry.path)
                elif stat.S_ISREG(metadata.st_mode):
                    name = Path(entry.path).relative_to(root).as_posix()
                    files[f"{prefix}/{name}"] = metadata.st_mtime
        if not pending:
            return files
        entries = os.scandir(pending.pop())


class Command(BaseCommand):
    help = "Report unreferenced files in service logo storage without changing files or rows."

    def handle(self, *args, **options):
        field = Service._meta.get_field("logo_file")
        storage = field.storage
        if not isinstance(storage, FileSystemStorage):
            raise CommandError("Service logo inventory incomplete: filesystem storage is required")

        using = router.db_for_write(Service)
        try:
            prefix = field.upload_to.rstrip("/")
            files = _file_mtimes(Path(storage.path(prefix)), prefix)
            referenced = set()
            if files:
                # One statement reads all references from a single snapshot on
                # every backend; Service rows are few compared to stored files.
                referenced.update(
                    Service.objects.using(using)
                    .exclude(logo_file="")
                    .order_by()
                    .values_list("logo_file", flat=True)
                    .distinct()
                )
        except (OSError, DatabaseError) as exc:
            raise CommandError(f"Service logo inventory incomplete: {exc}") from exc

        now = time()
        unreferenced = sorted(files.keys() - referenced)
        for name in unreferenced:
            age = max(0, int(now - files[name]))
            self.stdout.write(f"{json.dumps(name)} age_seconds={age}")
        self.stdout.write(f"{len(unreferenced)} of {len(files)} service logo files unreferenced on {using}.")
