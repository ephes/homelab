"""Two synthetic SQLite aliases used only by the migration regression lane."""

from copy import deepcopy

from config.settings.test import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
DATABASES["secondary"] = deepcopy(DATABASES["default"])
