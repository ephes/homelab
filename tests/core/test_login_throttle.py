"""Failed admin logins are limited per username and address, per address, and per network."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

LIMITS = {
    "HOMELAB_LOGIN_FAILURE_LIMIT": 3,
    "HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT": 5,
    "HOMELAB_LOGIN_NETWORK_FAILURE_LIMIT": 7,
    "HOMELAB_LOGIN_FAILURE_WINDOW_SECONDS": 900,
}
PASSWORD = "correct horse battery staple"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def small_limits():
    with override_settings(**LIMITS):
        yield


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_superuser(username="owner", email="owner@example.com", password=PASSWORD)


def login(address, username="owner", password=PASSWORD, forwarded=None):
    """POST the admin login form as Traefik would forward it from ``address``."""
    client = Client()
    response = client.post(
        reverse("admin:login"),
        {"username": username, "password": password, "next": reverse("admin:index")},
        HTTP_X_FORWARDED_FOR=forwarded or address,
    )
    return response.status_code == 302 and "_auth_user_id" in client.session


def fail(address, times, username="owner", forwarded=None):
    for _ in range(times):
        assert not login(address, username=username, password="wrong", forwarded=forwarded)


def test_correct_password_is_refused_after_too_many_failures_from_that_address(owner):
    fail("192.168.178.50", 3)

    assert not login("192.168.178.50")


def test_other_addresses_keep_their_own_budget(owner):
    fail("192.168.178.50", 3)

    assert login("192.168.178.51")


def test_failures_below_the_limit_do_not_lock_the_account(owner):
    fail("192.168.178.50", 2)

    assert login("192.168.178.50")


def test_success_resets_the_username_budget_for_that_address(owner):
    fail("192.168.178.50", 2)
    assert login("192.168.178.50")
    fail("192.168.178.50", 2)

    assert login("192.168.178.50")


def test_address_budget_covers_many_usernames(owner):
    for index in range(5):
        assert not login("100.100.1.2", username=f"guess{index}", password="wrong")

    assert not login("100.100.1.2")
    assert login("100.100.1.3")


def test_refused_attempt_does_not_verify_the_password(owner, monkeypatch):
    fail("192.168.178.50", 3)
    calls = []
    import django.contrib.auth.base_user as base_user

    original = base_user.check_password
    monkeypatch.setattr(
        base_user, "check_password", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs)
    )

    assert not login("192.168.178.50")
    assert calls == []


def test_window_expiry_restores_the_budget(owner, monkeypatch):
    import apps.core.login_throttle as throttle

    clock = [1_000_000.0]
    monkeypatch.setattr(throttle.time, "time", lambda: clock[0])
    fail("192.168.178.50", 3)
    assert not login("192.168.178.50")

    clock[0] += LIMITS["HOMELAB_LOGIN_FAILURE_WINDOW_SECONDS"] + 1

    assert login("192.168.178.50")


def test_only_the_address_traefik_appended_counts(owner):
    # Entries left of the last one are client-supplied and must not open new budgets.
    fail("ignored", 1, forwarded="203.0.113.1, 192.168.178.50")
    fail("ignored", 1, forwarded="203.0.113.2, 192.168.178.50")
    fail("ignored", 1, forwarded="not-an-ip, 192.168.178.50")

    assert not login("192.168.178.50")


def test_one_lan_ipv6_device_cannot_lock_out_the_others(owner):
    # Every LAN device shares the ULA /64; the username budget is per address.
    fail("fd50:3e45:c454:0::1", 3)

    assert not login("fd50:3e45:c454:0::1")
    assert login("fd50:3e45:c454:0::2")


def test_rotating_addresses_in_one_ipv6_slash64_exhausts_the_network_budget(owner):
    for host in range(1, 8):
        fail(f"2001:db8:1:2::{host}", 1)

    assert not login("2001:db8:1:2::99")
    assert login("2001:db8:1:3::99")


def test_rotating_addresses_in_one_ipv4_slash24_exhausts_the_network_budget(owner):
    for host in range(1, 8):
        fail(f"192.168.178.{host}", 1)

    assert not login("192.168.178.99")
    assert login("192.168.179.99")


def test_tailscale_ipv4_addresses_have_no_shared_network_budget(owner):
    for host in range(1, 9):
        fail(f"100.100.1.{host}", 1)

    assert login("100.100.1.99")


def test_tailscale_ipv6_addresses_have_no_shared_network_budget(owner):
    # All tailnet nodes share one /64, but each node's address is authenticated.
    for host in range(1, 9):
        fail(f"fd7a:115c:a1e0::{host}", 1)

    assert login("fd7a:115c:a1e0::99")


def test_ipv4_mapped_address_counts_as_the_ipv4_address(owner):
    fail("::ffff:192.168.178.50", 3)

    assert not login("192.168.178.50")


def test_disabled_limit_does_not_throttle(owner):
    with override_settings(HOMELAB_LOGIN_FAILURE_LIMIT=0):
        fail("192.168.178.50", 4)
        assert login("192.168.178.50")


def test_production_and_base_settings_enable_the_throttle():
    from django.conf import settings

    assert settings.AUTHENTICATION_BACKENDS[0] == "apps.core.login_throttle.LoginThrottleBackend"
    # Sessions created before the throttle keep working through the plain backend.
    assert "django.contrib.auth.backends.ModelBackend" in settings.AUTHENTICATION_BACKENDS


def test_default_limits():
    from config.settings import base

    assert base.HOMELAB_LOGIN_FAILURE_LIMIT == 5
    assert base.HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT == 30
    assert base.HOMELAB_LOGIN_NETWORK_FAILURE_LIMIT == 100
    assert base.HOMELAB_LOGIN_FAILURE_WINDOW_SECONDS == 15 * 60
