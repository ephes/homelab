"""
Legacy WSGI entrypoint, kept for launchers that still import ``homelab.wsgi``.

The canonical entrypoint is ``src.config.wsgi:application``. This module
serves the same application with the same default settings
(``config.settings.production``) instead of the retired ``homelab.settings``.
"""

from django.core.wsgi import get_wsgi_application

from ._canonical import configure

configure()

application = get_wsgi_application()
