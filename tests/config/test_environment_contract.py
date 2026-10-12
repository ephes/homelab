"""The environment templates and docs must name variables the settings really read."""

import re

import pytest

from .isolation import REPO_ROOT, load_settings, make_project_root, settings_module_bootstrap

SETTINGS_DIR = REPO_ROOT / "src" / "config" / "settings"
ENV_READ = re.compile(r"""\benv(?:\.[a-z_]+)?\(\s*["']([A-Z][A-Z0-9_]*)["']""")
ASSIGNMENT = re.compile(r"^\s*([A-Z][A-Z0-9_]*)=([^#\n]*)", re.MULTILINE)
FENCED_BLOCK = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)

# Read without a literal env("...") call: django-environ's env.db() default
# variable, and the variable Django itself uses to pick the settings module.
IMPLICITLY_READ = {"DATABASE_URL", "DJANGO_SETTINGS_MODULE"}


def consumed_variables() -> set[str]:
    names = set(IMPLICITLY_READ)
    for path in SETTINGS_DIR.glob("*.py"):
        names.update(ENV_READ.findall(path.read_text()))
    return names


def assignments(text: str) -> dict[str, str]:
    return {name: value.strip() for name, value in ASSIGNMENT.findall(text)}


def markdown_section(path, heading: str) -> str:
    text = path.read_text()
    start = text.index(heading)
    following = text.find("\n## ", start + len(heading))
    return text[start:] if following == -1 else text[start:following]


def fenced_assignments(markdown: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for block in FENCED_BLOCK.findall(markdown):
        found.update(assignments(block))
    return found


def test_settings_consume_the_expected_core_variables():
    # guards the scanner itself: an empty result would make the tests below vacuous
    assert {"DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_SECURE_SSL_REDIRECT"} <= consumed_variables()
    assert "DEBUG" not in consumed_variables()
    assert "DJANGO_DEBUG" not in consumed_variables()


@pytest.mark.parametrize(
    "template",
    [".env.example", "deploy/templates/env.template.j2"],
)
def test_environment_template_only_names_variables_the_settings_read(template):
    names = set(assignments((REPO_ROOT / template).read_text()))

    assert names, template
    assert names - consumed_variables() == set()


def test_configuration_doc_only_names_variables_the_settings_read():
    text = (REPO_ROOT / "docs" / "configuration.md").read_text()
    names = set(fenced_assignments(text))

    assert {"DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_SECURE_SSL_REDIRECT"} <= names
    assert names - consumed_variables() == set()


def test_documented_production_environment_configures_production(tmp_path):
    section = markdown_section(REPO_ROOT / "docs" / "configuration.md", "## Production Security")
    documented = fenced_assignments(section)
    assert set(documented) == {"DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_SECURE_SSL_REDIRECT"}
    root = make_project_root(tmp_path)

    settings = load_settings(root, settings_module_bootstrap("config.settings.production"), documented)

    assert settings["SECRET_KEY"] == documented["DJANGO_SECRET_KEY"]
    assert settings["ALLOWED_HOSTS"] == [documented["DJANGO_ALLOWED_HOSTS"]]
    assert settings["SECURE_SSL_REDIRECT"] is True
    assert settings["DEBUG"] is False


def test_ssl_redirect_follows_the_documented_variable(tmp_path):
    root = make_project_root(tmp_path)
    env = {"DJANGO_SECRET_KEY": "synthetic-contract-key", "DJANGO_SECURE_SSL_REDIRECT": "False"}

    settings = load_settings(root, settings_module_bootstrap("config.settings.production"), env)

    assert settings["SECURE_SSL_REDIRECT"] is False


@pytest.mark.parametrize(
    ("settings_module", "expected_debug"),
    [("config.settings.local", True), ("config.settings.production", False), ("config.settings.test", False)],
)
@pytest.mark.parametrize("variable", ["DEBUG", "DJANGO_DEBUG"])
@pytest.mark.parametrize("value", ["True", "False"])
def test_debug_is_decided_by_the_settings_module_not_the_environment(
    tmp_path, settings_module, expected_debug, variable, value
):
    root = make_project_root(tmp_path)
    env = {"DJANGO_SECRET_KEY": "synthetic-contract-key", variable: value}

    settings = load_settings(root, settings_module_bootstrap(settings_module), env)

    assert settings["DEBUG"] is expected_debug


def test_base_settings_never_enable_debug_from_the_environment(tmp_path):
    root = make_project_root(tmp_path)

    settings = load_settings(root, settings_module_bootstrap("config.settings.base"), {"DEBUG": "True"})

    assert settings["DEBUG"] is False
