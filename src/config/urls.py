"""
URL configuration for homelab project.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from config.media import serve_media

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns

# Serve media files (for low-traffic homelab, this is fine in production too).
# Note: static() only works when DEBUG=True, so we add it unconditionally for homelab.
# serve_media adds nosniff + a sandboxing CSP so uploaded files (e.g. SVG logos)
# cannot run script same-origin when opened directly.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_media),
]
