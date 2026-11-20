import errno
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import IntegrityError, OperationalError, connection, transaction

from apps.core.management.commands import add_default_services
from apps.core.models import Service

LOGOS = Path(__file__).resolve().parents[2] / "src" / "apps" / "core" / "static" / "core" / "logos"
RUSTFS_DESCRIPTION = (
    "S3-compatible object storage (RustFS on Fractal) for backups and application data. "
    "S3 API at https://s3.home.xn--wersdrfer-47a.de/ (LAN and Tailnet, signed requests only, no web console)"
)


def test_add_default_services_includes_opsgate():
    call_command("add_default_services")

    opsgate = Service.objects.get(name="OpsGate")

    assert opsgate.description == "Approval queue and audit surface for human-reviewed operator actions"
    assert opsgate.url == "https://opsgate.home.xn--wersdrfer-47a.de/"
    assert opsgate.icon == "fas fa-clipboard-check"
    assert opsgate.is_active is True
    assert opsgate.order == 25


def test_reseeding_preserves_owner_edits_and_adds_missing_defaults():
    call_command("add_default_services", stdout=StringIO())
    service = Service.objects.get(name="Fractal IPMI")
    service.description = "Owner description"
    service.url = "https://example.invalid/"
    service.icon = "fas fa-question"
    service.is_active = False
    service.order = 99
    service.save()
    before = Service.objects.values().get(pk=service.pk)
    Service.objects.get(name="Work").delete()

    call_command("add_default_services", stdout=StringIO())

    assert Service.objects.values().get(pk=service.pk) == before
    assert Service.objects.get(name="Work").order == 30


@pytest.mark.parametrize("owner_logo", [False, True])
def test_reseeding_backfills_only_missing_logos(owner_logo):
    service = Service.objects.create(
        name="Fractal IPMI",
        description="Owner",
        url="https://example.invalid/",
        icon="fas fa-question",
        is_active=False,
        order=99,
    )
    if owner_logo:
        service.logo_file.save("owner.svg", ContentFile(b"owner logo"), save=True)
    old_name = service.logo_file.name
    before = Service.objects.values("description", "url", "icon", "is_active", "order").get(pk=service.pk)

    call_command("add_default_services", stdout=StringIO())

    service.refresh_from_db()
    assert Service.objects.values(*before).get(pk=service.pk) == before
    assert service.logo_file.storage.exists(service.logo_file.name)
    if owner_logo:
        assert service.logo_file.name == old_name
        with service.logo_file.open("rb") as source:
            assert source.read() == b"owner logo"
    else:
        assert Path(service.logo_file.name).name.startswith("fractal-ipmi")


@pytest.mark.parametrize("owner_logo", [False, True])
def test_logo_copy_preserves_intervening_owner_save(logo_dir, monkeypatch, owner_logo):
    service = Service.objects.create(name="Home Assistant", description="Before", order=1)
    storage = Service._meta.get_field("logo_file").storage
    original_open = storage.open
    edits = []

    def open_after_owner_save(name, mode="rb"):
        if mode == "wb" and not edits:
            current = Service.objects.get(pk=service.pk)
            current.description = "Owner description"
            current.url = "https://owner.example/"
            current.order = 99
            current.is_active = False
            if owner_logo:
                current.logo_file.save("owner.svg", ContentFile(b"owner logo"), save=False)
            current.save()
            edits.append(Service.objects.values().get(pk=service.pk))
        return original_open(name, mode)

    # Interleave a real model save after the seed read, during storage I/O.
    # SQLite serializes independent writers; this deterministic seam also
    # exercises the stale snapshot possible on row-locking databases.
    monkeypatch.setattr(storage, "open", open_after_owner_save)
    original_chunks = File.chunks
    monkeypatch.setattr(
        File,
        "chunks",
        lambda self, chunk_size=None: iter([b"synthetic seed logo"])
        if self.name
        else original_chunks(self, chunk_size),
    )
    call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert len(edits) == 1
    after = Service.objects.values().get(pk=service.pk)
    before = edits[0]
    for field in before.keys() - {"logo_file", "updated_at"}:
        assert after[field] == before[field]
    service.refresh_from_db()
    with service.logo_file.open("rb") as source:
        assert source.read() == (b"owner logo" if owner_logo else b"synthetic seed logo")
    if owner_logo:
        assert after == before
    else:
        assert after["updated_at"] > before["updated_at"]
    referenced = set(Service.objects.exclude(logo_file="").values_list("logo_file", flat=True))
    assert {"services/logos/" + name for name in stored_logos(logo_dir)} == referenced


def test_add_default_services_includes_work_app():
    call_command("add_default_services")

    work = Service.objects.get(name="Work")

    assert work.url == "https://work.home.xn--wersdrfer-47a.de/"
    assert work.icon == "fas fa-tasks"
    assert work.is_active is True
    assert work.order == 30


# --- logo files and transaction rollback ---------------------------------------------


@pytest.fixture
def logo_dir(settings, tmp_path):
    """Give each test its own empty MEDIA_ROOT and return the logo upload directory."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path / "services" / "logos"


def stored_logos(logo_dir):
    return sorted(path.name for path in logo_dir.iterdir()) if logo_dir.exists() else []


def test_compensated_seed_name_is_not_deleted_again_after_later_failure(logo_dir, monkeypatch):
    service = Service.objects.create(name="Home Assistant")
    storage = service.logo_file.storage
    original_save, original_open, original_delete = storage.save, storage.open, storage.delete
    reserved, reused, deleted = [], [], []

    def save(name, content, max_length=None):
        if reused:
            raise OSError("later synthetic allocation failure")
        allocated = original_save(name, content, max_length=max_length)
        reserved.append(allocated)
        return allocated

    def open_after_competing_logo(name, mode="rb"):
        if mode == "wb" and name == reserved[0]:
            current = Service.objects.get(pk=service.pk)
            current.logo_file = original_save("services/logos/owner.svg", ContentFile(b"owner"))
            current.save()
        return original_open(name, mode)

    def delete_then_reuse(name):
        deleted.append(name)
        original_delete(name)
        if not reused:
            # Another allocation exists before its database reference commits.
            reused.append(original_save(name, ContentFile(b"other writer")))

    monkeypatch.setattr(storage, "save", save)
    monkeypatch.setattr(storage, "open", open_after_competing_logo)
    monkeypatch.setattr(storage, "delete", delete_then_reuse)
    original_chunks = File.chunks
    monkeypatch.setattr(
        File,
        "chunks",
        lambda self, chunk_size=None: iter([b"synthetic logo"]) if self.name else original_chunks(self, chunk_size),
    )
    with pytest.raises(OSError, match="later synthetic allocation failure"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert reused == reserved
    assert deleted == reserved
    assert storage.exists(reused[0])
    with storage.open(reused[0], "rb") as source:
        assert source.read() == b"other writer"


def fail_logo_save_on_call(monkeypatch, failing_call):
    """Let the storage reserve names until the given call, which fails before creating a file."""
    storage = Service._meta.get_field("logo_file").storage
    original = storage.save
    calls = []

    def save(name, content, max_length=None):
        calls.append(name)
        if len(calls) == failing_call:
            raise OSError("storage is full")
        return original(name, content, max_length=max_length)

    monkeypatch.setattr(storage, "save", save)
    return calls


@pytest.mark.django_db(transaction=True)
def test_failed_logo_save_rolls_back_without_success_output(logo_dir, monkeypatch):
    stdout, stderr = StringIO(), StringIO()
    with monkeypatch.context() as patch:
        calls = fail_logo_save_on_call(patch, failing_call=3)
        with pytest.raises(OSError, match="storage is full"):
            call_command("add_default_services", stdout=stdout, stderr=stderr)

    assert len(calls) == 3
    assert Service.objects.count() == 0
    assert stored_logos(logo_dir) == []
    assert stderr.getvalue().count("Removed logo file") == 2
    assert stdout.getvalue() == ""

    with transaction.atomic():
        call_command("add_default_services", stdout=stdout, stderr=stderr)
        assert stdout.getvalue() == ""

    output = stdout.getvalue().splitlines()
    for service in Service.objects.all():
        assert output.count(f"Created service: {service.name}") == 1
        if service.logo_file:
            assert output.count(f"Added logo for {service.name}") == 1
    assert output[-1] == f"Total services in database: {Service.objects.count()}"


def fail_logo_write_after_first_chunk(monkeypatch, failing_file):
    """Let the storage create the destination file, then fail while writing it (disk full)."""
    original = File.chunks
    opened = []

    def chunks(self, chunk_size=None):
        if not self.name:
            # The empty reservation file, not a logo source.
            yield from original(self, chunk_size)
            return
        opened.append(self.name)
        if len(opened) == failing_file:
            yield b"partial123"
            raise OSError(errno.ENOSPC, "No space left on device")
        yield from original(self, chunk_size)

    monkeypatch.setattr(File, "chunks", chunks)
    return opened


def test_partially_written_logo_is_removed_and_retry_reuses_its_name(logo_dir, monkeypatch):
    opened = fail_logo_write_after_first_chunk(monkeypatch, failing_file=3)

    with pytest.raises(OSError, match="No space left"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert len(opened) == 3
    assert Service.objects.count() == 0
    # Neither the two complete logos nor the 10-byte partial third one are left.
    assert stored_logos(logo_dir) == []

    monkeypatch.undo()
    call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    names = sorted(
        Path(name).name for name in Service.objects.exclude(logo_file="").values_list("logo_file", flat=True)
    )
    assert names == stored_logos(logo_dir)
    partial_name = Path(opened[2]).name
    assert partial_name in names
    assert not [name for name in names if name.startswith(Path(partial_name).stem + "_")]


def test_short_write_rolls_back_seed_and_removes_partial_logo(logo_dir, monkeypatch):
    service = Service.objects.create(name="Home Assistant")
    storage = service.logo_file.storage
    original_open = storage.open

    @contextmanager
    def short_writing_open(name, mode="rb"):
        with original_open(name, mode) as destination:
            yield SimpleNamespace(write=lambda chunk: destination.write(chunk[:1]))

    monkeypatch.setattr(storage, "open", short_writing_open)

    with pytest.raises(OSError, match="Short write"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    service.refresh_from_db()
    assert not service.logo_file
    assert stored_logos(logo_dir) == []


def test_partial_write_never_removes_an_existing_logo_with_the_same_name(logo_dir, monkeypatch):
    existing = Service.objects.create(name="Keeps Its Logo", url="https://example.invalid/")
    existing.logo_file.save("home-assistant.png", ContentFile(b"my own logo"), save=True)
    fail_logo_write_after_first_chunk(monkeypatch, failing_file=1)

    with pytest.raises(OSError, match="No space left"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert stored_logos(logo_dir) == ["home-assistant.png"]
    assert (logo_dir / "home-assistant.png").read_bytes() == b"my own logo"


def test_name_taken_by_another_upload_before_a_failed_write_is_not_removed(logo_dir, monkeypatch):
    """Another upload takes the free name first; our write then fails on its own, suffixed file."""
    storage = Service._meta.get_field("logo_file").storage
    original = storage.get_available_name
    competing = []

    def get_available_name(name, max_length=None):
        available = original(name, max_length=max_length)
        if not competing:
            # The competing upload wins the race for exactly the name we were just offered.
            competing.append(available)
            target = Path(storage.path(available))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"someone else's upload")
        return available

    monkeypatch.setattr(storage, "get_available_name", get_available_name)
    fail_logo_write_after_first_chunk(monkeypatch, failing_file=1)

    with pytest.raises(OSError, match="No space left"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert Service.objects.count() == 0
    other = Path(competing[0]).name
    # The other upload is untouched and our suffixed partial file is gone.
    assert stored_logos(logo_dir) == [other]
    assert (logo_dir / other).read_bytes() == b"someone else's upload"


def test_failed_run_keeps_existing_services_and_logos(logo_dir, monkeypatch):
    existing = Service.objects.create(name="Home Assistant", description="mine", url="https://example.invalid/")
    existing.logo_file.save("home-assistant.png", ContentFile(b"my own logo"), save=True)
    unrelated = Service.objects.create(name="Unrelated", url="https://example.invalid/unrelated")
    unrelated.logo_file.save("unrelated.svg", ContentFile(b"<svg/>"), save=True)
    fail_logo_save_on_call(monkeypatch, failing_call=2)

    with pytest.raises(OSError):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert sorted(Service.objects.values_list("name", flat=True)) == ["Home Assistant", "Unrelated"]
    existing.refresh_from_db()
    assert existing.description == "mine"
    assert existing.logo_file.name == "services/logos/home-assistant.png"
    assert stored_logos(logo_dir) == ["home-assistant.png", "unrelated.svg"]
    assert (logo_dir / "home-assistant.png").read_bytes() == b"my own logo"


def test_failed_row_save_after_logo_was_stored_removes_that_logo(logo_dir, monkeypatch):
    original = Service.save

    def save(self, *args, **kwargs):
        if self.logo_file and self.name == "Jellyfin":
            raise IntegrityError("row save failed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Service, "save", save)

    with pytest.raises(IntegrityError):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert Service.objects.count() == 0
    assert stored_logos(logo_dir) == []


@pytest.mark.django_db(transaction=True)
def test_failure_after_commit_keeps_the_committed_logos(logo_dir, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("late failure")

    monkeypatch.setattr(type(Service.objects.all()), "count", fail)
    stderr = StringIO()

    # The final count runs outside the transaction: the services are committed and keep their logos.
    with pytest.raises(RuntimeError):
        call_command("add_default_services", stdout=StringIO(), stderr=stderr)

    assert stored_logos(logo_dir) != []
    assert "Removed logo file" not in stderr.getvalue()


def test_retry_after_failed_run_leaves_one_logo_per_service(logo_dir, monkeypatch):
    fail_logo_save_on_call(monkeypatch, failing_call=4)
    with pytest.raises(OSError):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())
    monkeypatch.undo()

    call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    with_logo = Service.objects.exclude(logo_file="")
    names = sorted(Path(name).name for name in with_logo.values_list("logo_file", flat=True))
    # Every stored file belongs to exactly one service: the failed run left no orphan
    # behind that would force suffixed duplicates such as jellyfin_a1B2c3D.svg.
    assert names == stored_logos(logo_dir)
    assert len(names) == len(set(names)) > 3
    assert "jellyfin.svg" in names and not [name for name in names if name.startswith("jellyfin_")]


def test_cleanup_failure_does_not_hide_the_original_error(logo_dir, monkeypatch):
    fail_logo_save_on_call(monkeypatch, failing_call=3)
    storage = Service._meta.get_field("logo_file").storage

    def delete(name):
        raise PermissionError("cannot delete")

    monkeypatch.setattr(storage, "delete", delete)
    stderr = StringIO()

    with pytest.raises(OSError, match="storage is full"):
        call_command("add_default_services", stdout=StringIO(), stderr=stderr)

    assert stderr.getvalue().count("Could not remove logo file") == 2


@pytest.mark.parametrize("delete_fails", [False, True])
def test_broken_cleanup_diagnostics_preserve_original_failure(logo_dir, monkeypatch, delete_fails):
    fail_logo_save_on_call(monkeypatch, failing_call=3)
    storage = Service._meta.get_field("logo_file").storage
    original_delete = storage.delete
    attempted = []

    def delete(name):
        attempted.append(name)
        if delete_fails and len(attempted) == 1:
            raise PermissionError("cannot delete")
        original_delete(name)

    class BrokenStderr(StringIO):
        def write(self, text):
            raise BrokenPipeError("stderr closed")

    monkeypatch.setattr(storage, "delete", delete)

    with pytest.raises(OSError, match="storage is full"):
        call_command("add_default_services", stdout=StringIO(), stderr=BrokenStderr())

    assert len(attempted) == 2
    assert Service.objects.count() == 0
    assert stored_logos(logo_dir) == ([Path(attempted[0]).name] if delete_fails else [])


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("lookup_fails", [False, True])
def test_seed_cleanup_checks_pending_logo_references_once(logo_dir, monkeypatch, lookup_fails):
    monkeypatch.setattr(File, "chunks", lambda self, chunk_size=None: iter([b"synthetic logo"]))
    pending = []
    cleanup_queries = []

    class FailingReporter(StringIO):
        def write(self, text):
            # After commit, simulate an intervening writer retaining only one logo.
            logos = Service.objects.exclude(logo_file="").order_by("pk")
            pending.extend(logos.values_list("logo_file", flat=True))
            logos.exclude(logo_file=pending[0]).update(logo_file="")
            raise BrokenPipeError("synthetic reporter failure")

    def observe_cleanup(execute, sql, params, many, context):
        if pending and sql.startswith("SELECT"):
            cleanup_queries.append(params)
            if lookup_fails:
                raise OperationalError("synthetic reference lookup failure")
        return execute(sql, params, many, context)

    stderr = StringIO()
    with (
        connection.execute_wrapper(observe_cleanup),
        pytest.raises(BrokenPipeError, match="synthetic reporter failure"),
    ):
        call_command("add_default_services", stdout=FailingReporter(), stderr=stderr)

    assert len(pending) > 2
    assert len(cleanup_queries) == 1
    assert set(cleanup_queries[0]) == set(pending)
    expected = pending if lookup_fails else pending[:1]
    assert stored_logos(logo_dir) == sorted(Path(name).name for name in expected)
    assert (logo_dir / Path(pending[0]).name).read_bytes() == b"synthetic logo"
    if lookup_fails:
        assert "synthetic reference lookup failure" in stderr.getvalue()


@pytest.mark.django_db(transaction=True)
def test_postcommit_callback_failure_keeps_referenced_logos(logo_dir, monkeypatch):
    from django.db.models.signals import post_save

    scheduled = []
    expected = {}

    def fail():
        raise RuntimeError("synthetic callback failed after commit")

    def schedule(sender, instance, using, **kwargs):
        if instance.logo_file:
            with instance.logo_file.open("rb") as source:
                expected[instance.logo_file.name] = source.read()
            if not scheduled:
                scheduled.append(using)
                transaction.on_commit(fail, using=using)

    # Synthetic logo bytes only; no deployed media or external services.
    monkeypatch.setattr(File, "chunks", lambda self, chunk_size=None: iter([b"synthetic logo"]))
    post_save.connect(schedule, sender=Service, weak=False)
    stderr = StringIO()
    try:
        with pytest.raises(RuntimeError, match="synthetic callback failed after commit"):
            call_command("add_default_services", stdout=StringIO(), stderr=stderr)
    finally:
        post_save.disconnect(schedule, sender=Service)

    assert scheduled == ["default"]
    assert expected
    assert Service.objects.count() > 0
    assert set(Service.objects.exclude(logo_file="").values_list("logo_file", flat=True)) == set(expected)
    storage = Service._meta.get_field("logo_file").storage
    for name, content in expected.items():
        with storage.open(name, "rb") as source:
            assert source.read() == content == b"synthetic logo"
    assert "Removed logo file" not in stderr.getvalue()


@pytest.mark.django_db(transaction=True)
def test_missing_packaged_logo_reports_fallback_without_interrupting_seed(logo_dir, tmp_path, monkeypatch, client):
    packaged_logos = tmp_path / "static" / "core" / "logos"
    packaged_logos.mkdir(parents=True)
    (packaged_logos / "available.svg").write_bytes(b"<svg/>")
    monkeypatch.setattr(
        add_default_services, "__file__", str(tmp_path / "management" / "commands" / "add_default_services.py")
    )
    monkeypatch.setattr(
        add_default_services.Command,
        "_default_services",
        lambda self: [
            {"name": "Fallback service", "icon": "fas fa-rocket", "logo_filename": "missing.svg"},
            {"name": "Logo service", "logo_filename": "available.svg"},
        ],
    )
    stdout, stderr = StringIO(), StringIO()

    call_command("add_default_services", stdout=stdout, stderr=stderr)

    fallback = Service.objects.get(name="Fallback service")
    assert fallback.is_active and not fallback.logo_file
    assert b'<i class="fas fa-rocket"></i>' in client.get("/").content
    with Service.objects.get(name="Logo service").logo_file.open("rb") as logo:
        assert logo.read() == b"<svg/>"
    assert "Created service: Fallback service" in stdout.getvalue()
    assert "Added logo for Logo service" in stdout.getvalue()
    assert stderr.getvalue().splitlines() == [
        "Missing packaged logo missing.svg for Fallback service (using icon fallback)"
    ]

    fallback.logo_file.save("custom.svg", ContentFile(b"<svg/>"))
    stderr = StringIO()
    call_command("add_default_services", stdout=StringIO(), stderr=stderr)
    fallback.refresh_from_db()
    assert Path(fallback.logo_file.name).name == "custom.svg"
    assert stderr.getvalue() == ""


# --- RustFS replaces the retired MinIO tile ------------------------------------------


def test_add_default_services_offers_rustfs_not_minio(logo_dir):
    call_command("add_default_services", stdout=StringIO())

    assert not Service.objects.filter(name="MinIO").exists()
    rustfs = Service.objects.get(name="RustFS")
    assert rustfs.description == RUSTFS_DESCRIPTION
    assert rustfs.url == ""
    assert rustfs.icon == "fas fa-database"
    assert rustfs.is_active is True
    assert rustfs.order == 8
    assert Path(rustfs.logo_file.name).name.startswith("rustfs")
    with rustfs.logo_file.open("rb") as stored:
        assert stored.read() == (LOGOS / "rustfs.png").read_bytes()


def test_rustfs_seed_matches_the_replacement_migration():
    from importlib import import_module

    migration = import_module("apps.core.migrations.0018_replace_minio_with_rustfs")

    assert migration.RUSTFS["description"] == RUSTFS_DESCRIPTION
    assert migration.RUSTFS["url"] == ""
    assert migration.RUSTFS["icon"] == "fas fa-database"


def test_renamed_minio_tile_gets_the_rustfs_logo_on_reseed(logo_dir):
    # The state the replacement migration leaves: the former MinIO row, renamed,
    # without a logo, keeping its owner-managed order and status.
    Service.objects.create(name="RustFS", description=RUSTFS_DESCRIPTION, icon="fas fa-database", order=8)

    call_command("add_default_services", stdout=StringIO())

    rustfs = Service.objects.get(name="RustFS")
    assert Path(rustfs.logo_file.name).name.startswith("rustfs")
    assert not Service.objects.filter(name="MinIO").exists()


def test_every_default_logo_is_packaged():
    logos_dir = Path(add_default_services.__file__).parent.parent.parent / "static" / "core" / "logos"
    missing = [
        service["logo_filename"]
        for service in add_default_services.Command()._default_services()
        if service.get("logo_filename") and not (logos_dir / service["logo_filename"]).is_file()
    ]

    assert missing == []
