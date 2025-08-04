"""
WSGI config for homelab project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
