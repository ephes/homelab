import errno
from io import StringIO
from pathlib import Path

import pytest
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import IntegrityError

from apps.core.models import Service


def test_add_default_services_includes_opsgate():
    call_command("add_default_services")

    opsgate = Service.objects.get(name="OpsGate")

    assert opsgate.description == "Approval queue and audit surface for human-reviewed operator actions"
    assert opsgate.url == "https://opsgate.home.xn--wersdrfer-47a.de/"
    assert opsgate.icon == "fas fa-clipboard-check"
    assert opsgate.is_active is True
    assert opsgate.order == 25


def test_add_default_services_updates_existing_opsgate():
    opsgate = Service.objects.create(
        name="OpsGate",
        description="outdated",
        url="https://example.invalid/",
        icon="fas fa-question",
        is_active=False,
        order=99,
    )

    call_command("add_default_services")

    opsgate.refresh_from_db()

    assert opsgate.description == "Approval queue and audit surface for human-reviewed operator actions"
    assert opsgate.url == "https://opsgate.home.xn--wersdrfer-47a.de/"
    assert opsgate.icon == "fas fa-clipboard-check"
    assert opsgate.is_active is False
    assert opsgate.order == 25


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


def test_failed_logo_save_removes_logos_stored_by_the_same_run(logo_dir, monkeypatch):
    calls = fail_logo_save_on_call(monkeypatch, failing_call=3)

    with pytest.raises(OSError, match="storage is full"):
        call_command("add_default_services", stdout=StringIO(), stderr=StringIO())

    assert len(calls) == 3
    assert Service.objects.count() == 0
    assert stored_logos(logo_dir) == []


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


def test_failure_after_commit_keeps_the_committed_logos(logo_dir, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("late failure")

    monkeypatch.setattr(Service.objects, "count", fail)
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
