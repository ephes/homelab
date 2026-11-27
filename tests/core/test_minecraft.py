import shutil
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import Service

UNIT = "minecraft-java.service"


@pytest.fixture
def power_url(settings):
    settings.MINECRAFT_CONTROL_UNIT = UNIT
    return reverse("core:minecraft-power")


@pytest.fixture
def systemctl():
    with patch("apps.core.minecraft.subprocess.run") as run:
        yield run


@pytest.fixture
def connect():
    with patch("apps.core.minecraft.socket.create_connection") as create_connection:
        yield create_connection


@pytest.mark.parametrize(
    ("stdout", "returncode", "expected"),
    [
        ("inactive", 3, "off"),
        ("failed", 3, "off"),
        ("activating", 3, "starting"),
        ("deactivating", 3, "stopping"),
        ("inactive", 4, "unknown"),
        ("maintenance", 3, "unknown"),
        ("", 1, "unknown"),
    ],
)
def test_status_maps_systemd_states(client, power_url, systemctl, connect, stdout, returncode, expected):
    systemctl.return_value = subprocess.CompletedProcess([], returncode, stdout + "\n")

    response = client.get(power_url)

    assert response.status_code == 200
    assert response.json() == {"state": expected, "active": False}
    assert "no-store" in response["Cache-Control"]
    assert systemctl.call_args.args == (["/usr/bin/systemctl", "is-active", UNIT],)
    connect.assert_not_called()


@pytest.mark.parametrize(
    ("connect_error", "expected"),
    [
        (None, "running"),
        (ConnectionRefusedError, "starting"),
        (TimeoutError, "unknown"),
        (socket.gaierror, "unknown"),
    ],
)
def test_active_status_checks_tcp_readiness(client, settings, power_url, systemctl, connect, connect_error, expected):
    settings.MINECRAFT_PORT_HOST = "127.0.0.2"
    settings.MINECRAFT_PORT = 25566
    systemctl.return_value = subprocess.CompletedProcess([], 0, "active\n")
    connect.side_effect = connect_error

    response = client.get(power_url)

    assert response.status_code == 200
    assert response.json() == {"state": expected, "active": True}
    connect.assert_called_once_with(("127.0.0.2", 25566), timeout=0.5)


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("systemctl", 2)])
def test_systemctl_errors(client, power_url, systemctl, connect, error):
    systemctl.side_effect = error

    assert client.get(power_url).json() == {"state": "unknown", "active": False}
    connect.assert_not_called()
    assert client.post(power_url, {"action": "start"}).status_code == 502


@pytest.mark.parametrize(("action", "state"), [("start", "starting"), ("stop", "stopping")])
def test_power_action(client, power_url, systemctl, action, state):
    systemctl.return_value = subprocess.CompletedProcess([], 0)

    response = client.post(power_url, {"action": action, "unit": "other.service"})

    assert response.status_code == 202
    assert response.json() == {"state": state}
    systemctl.assert_called_once()
    assert systemctl.call_args.args == (["/usr/bin/systemctl", "--no-block", action, UNIT],)
    assert not systemctl.call_args.kwargs.get("shell", False)
    assert 0 < systemctl.call_args.kwargs["timeout"] <= 5


def test_failed_power_action_hides_stderr(client, power_url, systemctl):
    systemctl.return_value = subprocess.CompletedProcess([], 1, stderr="<script>internal error</script>")

    response = client.post(power_url, {"action": "stop"})

    assert response.status_code == 502
    assert response.json() == {"error": "Minecraft-Befehl fehlgeschlagen."}


@pytest.mark.parametrize("data", [{}, {"action": "restart"}, {"action": "start other.service"}])
def test_invalid_power_action(client, power_url, systemctl, data):
    assert client.post(power_url, data).status_code == 400
    systemctl.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "POST", "HEAD", "PUT"])
def test_disabled_power_endpoint_returns_404_before_csrf_and_method_checks(settings, systemctl, connect, method):
    settings.MINECRAFT_CONTROL_UNIT = ""
    client = Client(enforce_csrf_checks=True)

    assert client.generic(method, reverse("core:minecraft-power")).status_code == 404
    systemctl.assert_not_called()
    connect.assert_not_called()


@pytest.mark.django_db
def test_power_action_requires_csrf_token_from_dashboard(power_url, systemctl):
    client = Client(enforce_csrf_checks=True)
    Service.objects.create(name="Minecraft")
    dashboard = client.get(reverse("core:home"))
    assert dashboard.status_code == 200

    assert client.post(power_url, {"action": "start"}).status_code == 403
    systemctl.assert_not_called()

    systemctl.return_value = subprocess.CompletedProcess([], 0)
    token = dashboard.cookies["csrftoken"].value
    response = client.post(power_url, {"action": "start", "csrfmiddlewaretoken": token})
    assert response.status_code == 202
    systemctl.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("unit", ["", UNIT])
def test_power_form_only_appears_on_configured_minecraft_tile(client, settings, unit):
    settings.MINECRAFT_CONTROL_UNIT = unit
    Service.objects.create(name="Minecraft")
    Service.objects.create(name="Minecraft Wiki", url="https://example.test/wiki")

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    _, minecraft_tile, wiki_tile = response.content.decode().split('<div class="service-card">')
    assert '<h3 class="service-name">Minecraft</h3>' in minecraft_tile
    assert 'id="minecraft-power"' not in wiki_tile
    assert (f'action="{reverse("core:minecraft-power")}"' in minecraft_tile) is bool(unit)
    assert ("core/js/minecraft.js" in minecraft_tile) is bool(unit)


def test_power_tile_startup_and_stop_confirmation():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the Minecraft tile script")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10, check=False).stdout
    if int(version.lstrip("v").split(".")[0] or 0) < 18:
        pytest.skip("The Minecraft tile script test needs Node.js 18 or newer (node --test)")

    subprocess.run([node, "--test", Path(__file__).with_name("test_minecraft_ui.cjs")], check=True, timeout=10)
