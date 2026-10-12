"""Run the CI management gates against isolated source copies."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.config.isolation import make_project_root

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def checkout(tmp_path):
    root = make_project_root(tmp_path)
    shutil.copy2(ROOT / "manage.py", root)
    return root


def run_gate(checkout, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("DJANGO_")}
    env.pop("PYTHONPATH", None)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    return subprocess.run(
        [sys.executable, "manage.py", *args], cwd=checkout, env=env, text=True, capture_output=True, timeout=30
    )


def test_current_system_and_migrations_pass(checkout):
    for args in [("check",), ("makemigrations", "--check", "--dry-run")]:
        result = run_gate(checkout, *args)
        assert result.returncode == 0, result.stdout + result.stderr
    assert not list(checkout.rglob("*.sqlite3"))


def test_uncommitted_model_change_fails_migration_gate(checkout):
    models = checkout / "src/apps/core/models.py"
    models.write_text(
        models.read_text().replace("    name =", "    gate_probe = models.BooleanField(default=False)\n    name =", 1)
    )
    result = run_gate(checkout, "makemigrations", "--check", "--dry-run")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "gate_probe" in result.stdout
    assert not list((checkout / "src/apps/core/migrations").glob("*gate_probe*"))


def test_invalid_configuration_fails_system_gate(checkout):
    urls = checkout / "src/config/urls.py"
    urls.write_text(urls.read_text() + '\nurlpatterns.append("invalid URL pattern")\n')
    result = run_gate(checkout, "check")
    assert result.returncode != 0
    assert "urls.E004" in result.stderr


def test_workflow_requires_both_gates():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert workflow["env"]["DJANGO_SETTINGS_MODULE"] == "config.settings.test"
    assert workflow["env"]["UV_FROZEN"] == "1"
    commands = [step.get("run") for step in workflow["jobs"]["python"]["steps"]]
    assert "uv run python manage.py check" in commands
    assert "uv run python manage.py makemigrations --check --dry-run" in commands
