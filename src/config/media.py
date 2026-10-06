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
"""

from django.conf import settings
from django.views.static import serve

MEDIA_CONTENT_SECURITY_POLICY = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"


def serve_media(request, path):
    """Serve a file from ``MEDIA_ROOT`` with hardening headers."""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = MEDIA_CONTENT_SECURITY_POLICY
    return response
