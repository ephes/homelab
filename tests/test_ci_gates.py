"""Run the CI management gates against isolated source copies."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings

from tests.config.isolation import make_project_root

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def checkout(tmp_path):
    root = make_project_root(tmp_path)
    shutil.copy2(ROOT / "manage.py", root)
    return root


def isolated_environment():
    env = {key: value for key, value in os.environ.items() if not key.startswith(("DJANGO_", "PYTEST_"))}
    env.pop("PYTHONPATH", None)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    return env


def run_gate(checkout, *args):
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=checkout,
        env=isolated_environment(),
        text=True,
        capture_output=True,
        timeout=30,
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


def test_workflow_audits_frozen_runtime_and_development_graph():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["audit"]
    assert 0 < job["timeout-minutes"] <= 15
    assert "permissions" not in job  # Inherit the read-only workflow token.
    steps = job["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    # Separate steps ensure a failed export stops the job before auditing.
    assert commands == [
        "uv export --frozen --all-groups --no-hashes --no-emit-project --output-file requirements-audit.txt",
        "uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -r requirements-audit.txt",
    ]
    assert not any(step.get("continue-on-error") or step.get("if") for step in steps)
    assert not job.get("continue-on-error")


def test_failing_committed_operation_breaks_applied_migration_lane(checkout):
    shutil.copytree(ROOT / "database_tests", checkout / "database_tests", ignore=shutil.ignore_patterns("__pycache__"))
    (checkout / "tests").mkdir()
    for name in ["__init__.py", "conftest.py"]:
        shutil.copy2(ROOT / "tests" / name, checkout / "tests" / name)
    shutil.copy2(ROOT / "pytest.ini", checkout)
    with override_settings(MIGRATION_MODULES={}):
        leaves = MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes("core")
    assert leaves
    migration = checkout / "src/apps/core/migrations" / f"probe_{uuid4().hex}.py"
    migration.write_text(
        "from django.db import migrations\n"
        "def fail(apps, schema_editor):\n"
        "    raise RuntimeError('synthetic migration operation failed')\n"
        "class Migration(migrations.Migration):\n"
        f"    dependencies = {leaves!r}\n"
        "    operations = [migrations.RunPython(fail)]\n"
    )
    drift = run_gate(checkout, "makemigrations", "--check", "--dry-run")
    assert drift.returncode == 0, drift.stdout + drift.stderr
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "database_tests/test_applied_migrations.py", "--migrations", "--create-db"],
        cwd=checkout,
        env=isolated_environment(),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "synthetic migration operation failed" in result.stdout


def test_workflow_requires_executed_database_lanes():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["python"]["steps"]
    for command in [
        "uv run pytest database_tests/test_admin_contention.py --create-db",
        "uv run pytest database_tests/test_applied_migrations.py --migrations --create-db",
    ]:
        step = next(step for step in steps if step.get("run") == command)
        assert not step.get("if") and not step.get("continue-on-error")
