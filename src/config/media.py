"""
Hardened media file serving.

Homelab serves ``MEDIA_ROOT`` from Django in every environment (low traffic,
no separate media server). Uploaded files such as SVG service logos would
otherwise be rendered same-origin when opened directly, so every media
response is locked down:

- ``X-Content-Type-Options: nosniff`` stops browsers from guessing a more
  dangerous content type.
- ``Content-Security-Policy: sandbox; default-src 'none'; ...`` makes a media
  document opened directly (for example an SVG with embedded script) run in an
  opaque origin with scripts and outbound loads disabled. Embedding the files
  via ``<img>`` (how logos are shown on the dashboard) is unaffected.

Paths resolving outside ``MEDIA_ROOT`` are rejected; internal symlinks are
supported by resolving them once, then walking the canonical path without
following links. Only the verified opened regular file is streamed.
"""

import mimetypes
import os
import posixpath
import stat
from io import BufferedReader, FileIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since

MEDIA_CONTENT_SECURITY_POLICY = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"


def _open_regular_file(path):
    """Open a canonical path without following replacement links (POSIX)."""
    expected = path.stat()
    if not stat.S_ISREG(expected.st_mode):
        raise Http404("Media path is not a regular file")
    # Walk from the filesystem anchor, including MEDIA_ROOT's ancestors, so
    # O_NOFOLLOW protects every component rather than just the final filename.
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        raw = FileIO(descriptor, "rb")
    except BaseException:
        # FileIO leaves a supplied descriptor open if construction fails.
        os.close(descriptor)
        raise
    try:
        source = BufferedReader(raw)
    except BaseException:
        # A wrapper may already have closed raw during failed construction;
        # closing the owning object again is safe even if the fd was reused.
        raw.close()
        raise
    try:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(expected, opened):
            raise Http404("Media file changed while opening")
    except BaseException:
        source.close()
        raise
    return source, opened


def serve_media(request, path):
    """Serve a file from ``MEDIA_ROOT`` with hardening headers."""
    # Match Django's static path normalization, then check symlink targets.
    normalized_path = posixpath.normpath(path).lstrip("/")
    if ".." in Path(normalized_path).parts:
        raise SuspiciousFileOperation("Media path traversal")
    try:
        root = Path(settings.MEDIA_ROOT).resolve()
        resolved_path = (root / normalized_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise Http404("Invalid media path") from exc
    if not resolved_path.is_relative_to(root):
        raise Http404("Media path outside root")
    try:
        source, opened = _open_regular_file(resolved_path)
    except (OSError, ValueError) as exc:
        raise Http404("Media file unavailable") from exc
    try:
        if not was_modified_since(request.META.get("HTTP_IF_MODIFIED_SINCE"), opened.st_mtime):
            source.close()
            response = HttpResponseNotModified()
        else:
            content_type, encoding = mimetypes.guess_type(normalized_path)
            response = FileResponse(
                source, content_type=content_type or "application/octet-stream", filename=normalized_path
            )
            response["Last-Modified"] = http_date(opened.st_mtime)
            if encoding:
                response["Content-Encoding"] = encoding
    except BaseException:
        source.close()
        raise
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = MEDIA_CONTENT_SECURITY_POLICY
    return response
