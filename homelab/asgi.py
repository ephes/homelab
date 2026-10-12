"""
Legacy ASGI entrypoint, kept for launchers that still import ``homelab.asgi``.

The project is deployed through WSGI (``src.config.wsgi:application``). This
module serves the same project with the same default settings
(``config.settings.production``) instead of the retired ``homelab.settings``.
"""

from django.core.asgi import get_asgi_application

from ._canonical import configure

configure()

application = get_asgi_application()
