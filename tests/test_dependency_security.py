"""Keep the documentation parser on the reviewed security baseline."""

import tomllib
from pathlib import Path

from bs4 import BeautifulSoup
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def test_documentation_parser_security_floor():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    versions = {package["name"]: Version(package["version"]) for package in lock["package"]}
    assert versions["soupsieve"] >= Version("4.1")
    assert versions["beautifulsoup4"] >= Version("4.15.0")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for requirement in (project["project"]["requires-python"], lock["requires-python"]):
        supported = SpecifierSet(requirement)
        assert "3.11.4" not in supported
        assert "3.12" in supported


def test_beautifulsoup_css_selection_with_soupsieve():
    soup = BeautifulSoup('<section><div><div class="service">Homelab</div></div></section>', "html.parser")
    assert [node.text for node in soup.select("section div div.service")] == ["Homelab"]
    assert soup.select_one("section .service").text == "Homelab"
