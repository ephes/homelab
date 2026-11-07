"""Two synthetic SQLite aliases used by migration and runtime admin regression lanes."""

from copy import deepcopy

from config.settings.test import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
DATABASES["secondary"] = deepcopy(DATABASES["default"])
