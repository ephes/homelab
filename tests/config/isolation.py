"""
Run settings code in a separate interpreter against a synthetic project root.

The settings locate the project root from their own file path and read the
dotenv file there, so a faithful test needs a copy of the code in a directory
it controls. Nothing here reads the checkout's own ``.env`` or the developer's
environment.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

REPORTED_SETTINGS = (
    "SETTINGS_MODULE",
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "DATABASES",
    "ROOT_URLCONF",
    "INSTALLED_APPS",
    "SECURE_SSL_REDIRECT",
)

REPORT_SNIPPET = f"""
import json
from django.conf import settings
names = {REPORTED_SETTINGS!r}
print("SETTINGS-REPORT " + json.dumps({{name: getattr(settings, name, None) for name in names}}, default=str))
"""


def make_project_root(tmp_path: Path) -> Path:
    """Copy the importable code (no dotenv, database or media) into ``tmp_path``."""
    root = tmp_path / "project"
    ignore = shutil.ignore_patterns("__pycache__", ".env", "*.sqlite3", "media", "test_media", "staticfiles")
    shutil.copytree(REPO_ROOT / "src", root / "src", ignore=ignore)
    shutil.copytree(REPO_ROOT / "homelab", root / "homelab", ignore=ignore)
    assert not (root / ".env").exists()
    assert not (root / "src" / ".env").exists()
    return root


def run_python(root: Path, code: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in ``root`` with only the given variables exported."""
    process_env = {"PYTHONPATH": str(root / "src"), "PYTHONDONTWRITEBYTECODE": "1", **(env or {})}
    return subprocess.run(
        [sys.executable, "-W", "always", "-c", code],
        cwd=root,
        env=process_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def load_settings(root: Path, bootstrap: str, env: dict[str, str] | None = None) -> dict:
    """Run ``bootstrap`` (which must configure Django) and return the selected settings."""
    result = run_python(root, bootstrap + REPORT_SNIPPET, env)
    assert result.returncode == 0, result.stderr
    report = [line for line in result.stdout.splitlines() if line.startswith("SETTINGS-REPORT ")]
    assert len(report) == 1, result.stdout
    return json.loads(report[0].removeprefix("SETTINGS-REPORT "))


def settings_module_bootstrap(module: str) -> str:
    return f"import os\nos.environ['DJANGO_SETTINGS_MODULE'] = {module!r}\n"
