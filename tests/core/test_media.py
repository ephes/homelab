import errno
import os
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile

from apps.core.models import Service
from config.media import MEDIA_CONTENT_SECURITY_POLICY

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"


def test_media_root_is_isolated_per_session(isolated_media_root):
    media_root = Path(settings.MEDIA_ROOT).resolve()

    assert media_root == Path(isolated_media_root).resolve()
    assert not media_root.is_relative_to(SOURCE_ROOT)


def test_uploaded_logo_is_written_to_isolated_media_root(isolated_media_root):
    service = Service.objects.create(name="Logo Service", url="https://example.com")
    service.logo_file.save("isolation-check.svg", ContentFile(b"<svg/>"), save=True)

    stored = Path(service.logo_file.path).resolve()

    assert stored.is_relative_to(Path(isolated_media_root).resolve())
    assert not stored.is_relative_to(SOURCE_ROOT)


def test_media_svg_is_served_with_hardening_headers(client, isolated_media_root):
    logos = Path(isolated_media_root) / "services" / "logos"
    logos.mkdir(parents=True, exist_ok=True)
    (logos / "evil.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')

    response = client.get("/media/services/logos/evil.svg")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
    assert MEDIA_CONTENT_SECURITY_POLICY.startswith("sandbox")
    assert "default-src 'none'" in MEDIA_CONTENT_SECURITY_POLICY


def test_media_not_modified_response_keeps_hardening_headers(client, isolated_media_root):
    (Path(isolated_media_root) / "cached.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    first = client.get("/media/cached.png")

    response = client.get("/media/cached.png", HTTP_IF_NONE_MATCH=first["ETag"])

    assert response.status_code == 304
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


def test_media_missing_file_returns_404(client):
    assert client.get("/media/missing.svg").status_code == 404


@pytest.mark.parametrize("error_type", [OSError, RuntimeError, ValueError])
def test_media_root_resolution_failure_returns_404(client, settings, tmp_path, monkeypatch, error_type):
    from config import media

    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"synthetic logo")
    original_resolve = Path.resolve
    failures = []

    def fail_root(self, *args, **kwargs):
        if self == tmp_path:
            failures.append(self)
            raise error_type("synthetic unavailable root")
        return original_resolve(self, *args, **kwargs)

    def unexpected_open(*args, **kwargs):
        pytest.fail("unresolved root must not open a file")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", fail_root)
        patch.setattr(media, "_open_regular_file", unexpected_open)
        assert client.get("/media/logo.svg").status_code == 404
    assert failures == [tmp_path]
    response = client.get("/media/logo.svg")
    try:
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == b"synthetic logo"
    finally:
        response.close()


def test_media_nul_path_returns_404(client):
    assert client.get("/media/a%00b").status_code == 404


@pytest.mark.parametrize("directory_link", [False, True])
def test_media_symlink_outside_root_returns_404(client, settings, tmp_path, directory_link):
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    outside = root.with_name(root.name + "-outside")
    outside.mkdir(exist_ok=True)
    sentinel = b"outside-media-sentinel"
    (outside / "secret.svg").write_bytes(sentinel)
    link = root / ("outside-directory" if directory_link else "outside-file.svg")
    link.symlink_to(outside if directory_link else outside / "secret.svg", target_is_directory=directory_link)

    response = client.get(f"/media/{link.name}" + ("/secret.svg" if directory_link else ""))

    assert response.status_code == 404
    assert sentinel not in response.content


@pytest.mark.parametrize("directory_link", [False, True])
def test_media_symlink_inside_root_is_served(client, settings, tmp_path, directory_link):
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    (root / "original.svg").write_bytes(b"<svg/>")
    if directory_link:
        (root / "linked").symlink_to(root, target_is_directory=True)
        url = "/media/linked/original.svg"
    else:
        (root / "linked.svg").symlink_to("original.svg")
        url = "/media/linked.svg"

    response = client.get(url)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"<svg/>"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
    cached = client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
    assert cached.status_code == 304
    assert cached["X-Content-Type-Options"] == "nosniff"
    assert cached["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


def test_media_path_traversal_is_rejected():
    from django.test import Client

    client = Client(raise_request_exception=False)

    response = client.get("/media/../config/settings/base.py")

    assert response.status_code == 400


@pytest.mark.parametrize("component", ["directory", "file"])
def test_media_path_swap_after_validation_is_refused(client, settings, tmp_path, monkeypatch, component):
    root = tmp_path / "media"
    logos = root / "logos"
    logos.mkdir(parents=True)
    settings.MEDIA_ROOT = root
    target = logos / "logo.svg"
    target.write_bytes(b"safe logo")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = b"outside sentinel"
    (outside / "logo.svg").write_bytes(sentinel)
    resolve = Path.resolve
    swapped = []

    def resolve_then_swap(self, *args, **kwargs):
        resolved = resolve(self, *args, **kwargs)
        if self == target and not swapped:
            swapped.append(True)
            if component == "directory":
                logos.rename(root / "retired")
                logos.symlink_to(outside, target_is_directory=True)
            else:
                target.unlink()
                target.symlink_to(outside / "logo.svg")
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_then_swap)
    response = client.get("/media/logos/logo.svg")
    body = b"".join(response.streaming_content) if response.streaming else response.content
    response.close()

    assert swapped
    assert sentinel not in body
    assert response.status_code == 404


def test_media_replaced_regular_file_identity_is_refused(client, settings, tmp_path, monkeypatch):
    import os

    from config import media

    settings.MEDIA_ROOT = tmp_path
    target = tmp_path / "logo.svg"
    target.write_bytes(b"original")
    replacement = tmp_path / "new.svg"
    replacement.write_bytes(b"replacement")
    original_open = os.open
    replaced = []

    def replace_then_open(path, flags, *args, **kwargs):
        if path == target.name and kwargs.get("dir_fd") is not None:
            replacement.replace(target)
            replaced.append(True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(media.os, "open", replace_then_open)
    response = client.get("/media/logo.svg")
    assert replaced
    assert response.status_code == 404


def test_media_stream_uses_opened_file_after_path_replacement(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    target = tmp_path / "logo.svg"
    target.write_bytes(b"original")
    response = client.get("/media/logo.svg")
    replacement = tmp_path / "new.svg"
    replacement.write_bytes(b"replacement")
    replacement.replace(target)
    try:
        assert b"".join(response.streaming_content) == b"original"
        assert response["Content-Length"] == str(len(b"original"))
    finally:
        response.close()


@pytest.mark.parametrize("conditional", [False, True])
def test_media_directory_is_never_served(client, settings, tmp_path, conditional):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logos").mkdir()
    headers = {"HTTP_IF_MODIFIED_SINCE": "Wed, 31 Dec 2098 23:59:59 GMT"} if conditional else {}
    assert client.get("/media/logos", **headers).status_code == 404


def test_media_encoded_file_retains_headers(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg.gz").write_bytes(b"compressed fixture")
    response = client.get("/media/logo.svg.gz", HTTP_IF_MODIFIED_SINCE="invalid date")
    try:
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert response["Content-Encoding"] == "gzip"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
        assert b"".join(response.streaming_content) == b"compressed fixture"
    finally:
        response.close()


def test_media_not_modified_closes_opened_descriptor(client, settings, tmp_path, monkeypatch):
    from config import media

    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"logo")
    opened = []
    original_open = media._open_regular_file

    def record_source(path):
        source, metadata = original_open(path)
        opened.append(source)
        return source, metadata

    monkeypatch.setattr(media, "_open_regular_file", record_source)
    response = client.get("/media/logo.svg")
    response.close()
    cached = client.get("/media/logo.svg", HTTP_IF_NONE_MATCH=response["ETag"])
    assert cached.status_code == 304
    assert len(opened) == 2
    assert all(source.closed for source in opened)


@pytest.mark.parametrize("error_type", [OverflowError, OSError, ValueError])
def test_media_invalid_date_keeps_etag_and_closes_source(client, settings, tmp_path, monkeypatch, error_type):
    from config import media

    settings.MEDIA_ROOT = tmp_path
    logo = tmp_path / "logo.svg"
    logo.write_bytes(b"synthetic logo")
    timestamp = 1_234_567_890
    os.utime(logo, (timestamp, timestamp))
    opened = []
    original_open = media._open_regular_file

    def record_source(path):
        source, metadata = original_open(path)
        opened.append(source)
        return source, metadata

    def reject_date(value):
        assert value == timestamp
        raise error_type("synthetic unsupported timestamp")

    monkeypatch.setattr(media, "_open_regular_file", record_source)
    monkeypatch.setattr(media, "http_date", reject_date)

    response = client.get("/media/logo.svg")
    try:
        assert response.status_code == 200
        assert not opened[0].closed
        assert b"".join(response.streaming_content) == b"synthetic logo"
    finally:
        response.close()
    assert opened[0].closed

    cached = client.get("/media/logo.svg", HTTP_IF_NONE_MATCH=response["ETag"])
    assert cached.status_code == 304
    assert len(opened) == 2
    assert opened[1].closed
    for result in (response, cached):
        assert result["ETag"] == response["ETag"]
        assert "Last-Modified" not in result
        assert result["X-Content-Type-Options"] == "nosniff"
        assert result["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


@pytest.mark.parametrize("stage", ["raw", "buffer", "closed_buffer"])
@pytest.mark.parametrize("error_type", [OSError, RuntimeError, MemoryError])
def test_media_wrapper_failure_closes_all_descriptors(client, settings, tmp_path, monkeypatch, error_type, stage):
    from config import media

    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"synthetic logo")
    original_open, original_close = media.os.open, media.os.close
    acquired, active, failures = [], {}, []
    error = error_type("synthetic wrapper failure")

    def record_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        record = {"descriptor": descriptor, "closes": 0}
        acquired.append(record)
        assert descriptor not in active
        active[descriptor] = record
        return descriptor

    def record_closed(descriptor):
        record = active.pop(descriptor)
        record["closes"] += 1

    def record_close(descriptor):
        record_closed(descriptor)
        original_close(descriptor)

    class TrackedFileIO(media.FileIO):
        def close(self):
            if not self.closed:
                descriptor = self.fileno()
                super().close()
                record_closed(descriptor)
            else:
                super().close()

    def fail_raw(descriptor, *args, **kwargs):
        assert descriptor in active
        failures.append(descriptor)
        raise error

    def fail_buffer(raw):
        assert raw.fileno() in active
        failures.append(raw.fileno())
        if stage == "closed_buffer":
            raw.close()
        raise error

    try:
        with monkeypatch.context() as patch:
            patch.setattr(media.os, "open", record_open)
            patch.setattr(media.os, "close", record_close)
            patch.setattr(media, "FileIO", fail_raw if stage == "raw" else TrackedFileIO)
            if stage != "raw":
                patch.setattr(media, "BufferedReader", fail_buffer)
            for _ in range(3):
                if error_type is OSError:
                    assert client.get("/media/logo.svg").status_code == 404
                else:
                    with pytest.raises(error_type) as caught:
                        client.get("/media/logo.svg")
                    assert caught.value is error
                assert not active
        assert len(failures) == 3
        assert acquired and all(record["closes"] == 1 for record in acquired)
    finally:
        # Keep failing counterfactuals from leaking descriptors in the test runner.
        for descriptor in active:
            original_close(descriptor)


@pytest.mark.parametrize("update", ["replace", "in_place"])
def test_media_same_second_generation_revalidation(client, settings, tmp_path, monkeypatch, update):
    import os

    from config import media

    settings.MEDIA_ROOT = tmp_path
    target = tmp_path / "logo.svg"
    target.write_bytes(b"old logo")
    second = 1800000000 * 10**9
    os.utime(target, ns=(second, second + 123000000))
    sources = []
    original_open = media._open_regular_file

    def record_open(path):
        source, metadata = original_open(path)
        sources.append(source)
        return source, metadata

    monkeypatch.setattr(media, "_open_regular_file", record_open)
    first = client.get("/media/logo.svg")
    try:
        assert first.status_code == 200
        old_tag, old_date = first["ETag"], first["Last-Modified"]
        if update == "replace":
            replacement = tmp_path / "new.svg"
            replacement.write_bytes(b"new logo")
            os.utime(replacement, ns=(second, second + 123000000))
            replacement.replace(target)  # Same size and exact mtime, new inode.
        else:
            target.write_bytes(b"new logo")
            os.utime(target, ns=(second, second + 456000000))
        # Atomic replacement preserves the already-opened generation.
        if update == "replace":
            assert b"".join(first.streaming_content) == b"old logo"
    finally:
        first.close()
    stale = client.get("/media/logo.svg", HTTP_IF_NONE_MATCH=old_tag, HTTP_IF_MODIFIED_SINCE=old_date)
    try:
        assert stale.status_code == 200
        assert not sources[-1].closed
        assert stale["Last-Modified"] == old_date
        assert stale["ETag"] != old_tag
        assert b"".join(stale.streaming_content) == b"new logo"
    finally:
        stale.close()
    current_tag = stale["ETag"]
    assert current_tag.startswith('W/"')
    for candidate in [current_tag, current_tag.removeprefix("W/"), f'"stale", {current_tag}', "*"]:
        current = client.get(
            "/media/logo.svg",
            HTTP_IF_NONE_MATCH=candidate,
            HTTP_IF_MODIFIED_SINCE="Thu, 01 Jan 1970 00:00:00 GMT",
        )
        assert current.status_code == 304
        assert sources[-1].closed
        assert current["ETag"] == current_tag
        assert current["Last-Modified"] == old_date
        assert current["X-Content-Type-Options"] == "nosniff"
        assert current["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
        current.close()
    assert all(source.closed for source in sources)
    assert stale["X-Content-Type-Options"] == "nosniff"
    assert stale["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


@pytest.mark.parametrize("tag", [None, '"stale"', "malformed", ""])
def test_media_date_only_cannot_hide_a_generation(client, settings, tmp_path, tag):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"logo")
    first = client.get("/media/logo.svg")
    first.close()
    headers = {"HTTP_IF_MODIFIED_SINCE": first["Last-Modified"]}
    if tag is not None:
        headers["HTTP_IF_NONE_MATCH"] = tag
    response = client.get("/media/logo.svg", **headers)
    try:
        assert response.status_code == 200
        assert response["ETag"] == first["ETag"]
        assert b"".join(response.streaming_content) == b"logo"
    finally:
        response.close()


@pytest.mark.parametrize(
    "headers",
    [
        {"HTTP_IF_UNMODIFIED_SINCE": "Thu, 01 Jan 1970 00:00:00 GMT"},
        {"HTTP_IF_UNMODIFIED_SINCE": "Wed, 31 Dec 2098 23:59:59 GMT"},
        {"HTTP_IF_MATCH": "current"},
        {"HTTP_IF_MATCH": '"stale"'},
    ],
)
def test_media_other_preconditions_keep_serving_full_content(client, settings, tmp_path, headers):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"logo")
    first = client.get("/media/logo.svg")
    first.close()
    if headers.get("HTTP_IF_MATCH") == "current":
        headers = {"HTTP_IF_MATCH": first["ETag"]}
    response = client.get("/media/logo.svg", **headers)
    try:
        assert response.status_code == 200
        assert response["ETag"] == first["ETag"]
        assert b"".join(response.streaming_content) == b"logo"
    finally:
        response.close()


def test_media_if_none_match_ignored_for_unsafe_methods(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "logo.svg").write_bytes(b"logo")
    first = client.get("/media/logo.svg")
    first.close()
    response = client.post("/media/logo.svg", HTTP_IF_NONE_MATCH=first["ETag"])
    assert response.status_code != 304
    response.close()


class DescriptorLedger:
    """Record every descriptor ``config.media`` acquires and every retirement.

    Raw descriptors are retired through ``os.close``; wrapped ones through the
    ``FileIO`` owner. Closing a number the ledger does not own is recorded as
    foreign and never reaches the OS, because that number may already belong to
    an unrelated file.
    """

    def __init__(self, media):
        self.media = media
        self.original_open, self.original_close = media.os.open, media.os.close
        self.acquired, self.active, self.foreign = [], {}, []
        self.on_close = None
        self.on_open = None
        ledger = self

        class TrackedFileIO(media.FileIO):
            def close(self):
                if not self.closed:
                    descriptor = self.fileno()
                    super().close()
                    ledger.retire(descriptor)
                else:
                    super().close()

        self.file_io = TrackedFileIO

    def open(self, path, flags, *args, **kwargs):
        descriptor = self.original_open(path, flags, *args, **kwargs)
        assert descriptor not in self.active
        record = {"descriptor": descriptor, "path": path, "closes": 0}
        self.acquired.append(record)
        self.active[descriptor] = record
        if self.on_open:
            self.on_open(descriptor, path, kwargs.get("dir_fd"))
        return descriptor

    def retire(self, descriptor):
        record = self.active.pop(descriptor, None)
        if record is None:
            self.foreign.append(descriptor)
            return False
        record["closes"] += 1
        return True

    def close(self, descriptor):
        if not self.retire(descriptor):
            raise OSError(errno.EBADF, "descriptor is not owned by this request")
        self.original_close(descriptor)
        if self.on_close:
            self.on_close(descriptor)

    def install(self, patch):
        patch.setattr(self.media.os, "open", self.open)
        patch.setattr(self.media.os, "close", self.close)
        patch.setattr(self.media, "FileIO", self.file_io)

    def assert_balanced(self):
        assert not self.active
        assert not self.foreign
        assert self.acquired and all(record["closes"] == 1 for record in self.acquired)

    def release_leaks(self):
        # Keep failing counterfactuals from leaking descriptors in the test runner.
        for descriptor in list(self.active):
            self.original_close(descriptor)


@pytest.mark.parametrize("stage", ["transfer", "final"])
@pytest.mark.parametrize("error_type", [OSError, RuntimeError])
def test_media_directory_close_failure_retires_each_descriptor_once(
    client, settings, tmp_path, monkeypatch, error_type, stage
):
    from config import media

    root = tmp_path / "media"
    (root / "services" / "logos").mkdir(parents=True)
    settings.MEDIA_ROOT = root
    (root / "services" / "logos" / "logo.svg").write_bytes(b"synthetic logo")
    ledger = DescriptorLedger(media)
    error = error_type("synthetic directory close failure")
    failures, request = [], {}

    def note_file_parent(descriptor, path, dir_fd):
        if path == "logo.svg":
            request["file_parent"] = dir_fd

    def fail_once(descriptor):
        # The descriptor is already released, as after close() reports EINTR/EIO
        # on Linux: retrying the number could close an unrelated reused file.
        if not request.get("armed"):
            return
        transfer = stage == "transfer" and "file_parent" not in request
        final = stage == "final" and descriptor == request.get("file_parent")
        if transfer or final:
            request["armed"] = False
            failures.append(descriptor)
            raise error

    ledger.on_open, ledger.on_close = note_file_parent, fail_once
    try:
        with monkeypatch.context() as patch:
            ledger.install(patch)
            for _ in range(2):
                request.clear()
                request["armed"] = True
                if error_type is OSError:
                    assert client.get("/media/services/logos/logo.svg").status_code == 404
                else:
                    with pytest.raises(error_type) as caught:
                        client.get("/media/services/logos/logo.svg")
                    assert caught.value is error
                assert not ledger.active
                assert not ledger.foreign
            request.clear()
            response = client.get("/media/services/logos/logo.svg")
            try:
                assert response.status_code == 200
                assert b"".join(response.streaming_content) == b"synthetic logo"
            finally:
                response.close()
        assert len(failures) == 2
        ledger.assert_balanced()
    finally:
        ledger.release_leaks()


@pytest.mark.parametrize("conditional", [False, True])
@pytest.mark.parametrize("other_link", ["outside", "inside"])
def test_media_hard_linked_file_is_refused(client, settings, tmp_path, monkeypatch, other_link, conditional):
    from config import media

    root = tmp_path / "media"
    logos = root / "services" / "logos"
    logos.mkdir(parents=True)
    settings.MEDIA_ROOT = root
    sentinel = b"hard-link canary"
    canary = (tmp_path / "outside-canary.svg") if other_link == "outside" else (logos / "original.svg")
    canary.write_bytes(sentinel)
    os.link(canary, logos / "linked.svg")
    headers = {"HTTP_IF_NONE_MATCH": "*"} if conditional else {}
    ledger = DescriptorLedger(media)
    try:
        with monkeypatch.context() as patch:
            ledger.install(patch)
            response = client.get("/media/services/logos/linked.svg", **headers)
            body = b"".join(response.streaming_content) if response.streaming else response.content
            response.close()
        assert response.status_code == 404
        assert sentinel not in body
        ledger.assert_balanced()
    finally:
        ledger.release_leaks()

    # Removing the second name restores an ordinary single-link logo.
    canary.unlink()
    served = client.get("/media/services/logos/linked.svg")
    try:
        assert served.status_code == 200
        assert b"".join(served.streaming_content) == sentinel
        cached = client.get("/media/services/logos/linked.svg", HTTP_IF_NONE_MATCH=served["ETag"])
        assert cached.status_code == 304
        assert cached["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
    finally:
        served.close()
