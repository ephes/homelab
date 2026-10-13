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

    response = client.get("/media/cached.png", HTTP_IF_MODIFIED_SINCE=first["Last-Modified"])

    assert response.status_code == 304
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


def test_media_missing_file_returns_404(client):
    assert client.get("/media/missing.svg").status_code == 404


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


def test_media_symlink_inside_root_is_served(client, settings, tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    (root / "original.svg").write_bytes(b"<svg/>")
    (root / "linked.svg").symlink_to("original.svg")

    response = client.get("/media/linked.svg")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"<svg/>"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY
    cached = client.get("/media/linked.svg", HTTP_IF_MODIFIED_SINCE=response["Last-Modified"])
    assert cached.status_code == 304
    assert cached["X-Content-Type-Options"] == "nosniff"
    assert cached["Content-Security-Policy"] == MEDIA_CONTENT_SECURITY_POLICY


def test_media_path_traversal_is_rejected():
    from django.test import Client

    client = Client(raise_request_exception=False)

    response = client.get("/media/../config/settings/base.py")

    assert response.status_code == 400
