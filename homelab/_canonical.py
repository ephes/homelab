"""Shared bootstrap for the legacy ``homelab.wsgi`` / ``homelab.asgi`` entrypoints."""

import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
CANONICAL_SETTINGS = "config.settings.production"


def configure() -> None:
    """
    Select the same configuration as ``src/config/wsgi.py``.

    The ``config`` package lives in ``src``. An explicitly exported
    DJANGO_SETTINGS_MODULE is kept; without one the production settings are
    used, never development settings.
    """
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", CANONICAL_SETTINGS)
