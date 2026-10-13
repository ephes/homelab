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
supported. This assumes stable paths between validation and opening the file
and does not prevent concurrent filesystem path replacement.
"""

import posixpath
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404
from django.views.static import serve

MEDIA_CONTENT_SECURITY_POLICY = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"


def serve_media(request, path):
    """Serve a file from ``MEDIA_ROOT`` with hardening headers."""
    root = Path(settings.MEDIA_ROOT).resolve()
    # Match Django's static path normalization, then check symlink targets.
    normalized_path = posixpath.normpath(path).lstrip("/")
    if ".." in Path(normalized_path).parts:
        raise SuspiciousFileOperation("Media path traversal")
    try:
        resolved_path = (root / normalized_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise Http404("Invalid media path") from exc
    if not resolved_path.is_relative_to(root):
        raise Http404("Media path outside root")
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = MEDIA_CONTENT_SECURITY_POLICY
    return response
