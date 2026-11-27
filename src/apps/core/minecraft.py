"""Read and control the local Minecraft systemd service."""

import socket
import subprocess

from django.conf import settings

SYSTEMD_STATES = {
    (3, "inactive"): "off",
    (3, "failed"): "off",
    (3, "activating"): "starting",
    (3, "deactivating"): "stopping",
}


def _systemctl(*args):
    return subprocess.run(
        ["/usr/bin/systemctl", *args, settings.MINECRAFT_CONTROL_UNIT],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=2,
        check=False,
    )


def status():
    try:
        result = _systemctl("is-active")
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unknown", "active": False}

    systemd_status = (result.returncode, result.stdout.strip())
    if systemd_status != (0, "active"):
        return {"state": SYSTEMD_STATES.get(systemd_status, "unknown"), "active": False}

    try:
        with socket.create_connection((settings.MINECRAFT_PORT_HOST, settings.MINECRAFT_PORT), timeout=0.5):
            state = "running"
    except ConnectionRefusedError:
        state = "starting"
    except (OSError, OverflowError):
        state = "unknown"
    return {"state": state, "active": True}


def set_power(action):
    try:
        return _systemctl("--no-block", action).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
