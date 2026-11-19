"""Concurrent failed logins on a real SQLite file cannot exceed a budget."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.models import LoginThrottleBucket

pytestmark = pytest.mark.django_db(transaction=True)
ATTEMPTS = 12
LIMIT = 4


def test_parallel_failures_are_charged_atomically():
    assert connection.vendor == "sqlite"
    assert "memory" not in str(connection.settings_dict["NAME"])
    get_user_model().objects.create_superuser(username="owner", email="o@example.com", password="right-password")
    start = Barrier(ATTEMPTS)

    def attempt(_):
        try:
            start.wait(10)
            response = Client(raise_request_exception=True).post(
                reverse("admin:login"),
                {"username": "owner", "password": "wrong-password", "next": "/admin/"},
                HTTP_X_FORWARDED_FOR="192.168.178.50",
            )
            return response.status_code
        finally:
            connections.close_all()

    with override_settings(HOMELAB_LOGIN_FAILURE_LIMIT=LIMIT, HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT=100):
        with ThreadPoolExecutor(max_workers=ATTEMPTS) as pool:
            statuses = list(pool.map(attempt, range(ATTEMPTS)))

    assert statuses == [200] * ATTEMPTS  # the login form re-renders with an error
    # One row each for the /24 network, the address and the username/address pair.
    assert sorted(LoginThrottleBucket.objects.values_list("failures", flat=True)) == [LIMIT, LIMIT, LIMIT]


def test_success_clears_only_pair_charges_through_its_reservation(monkeypatch):
    user_model = get_user_model()
    user_model.objects.create_superuser(username="owner", email="o@example.com", password="right-password")
    check_password = user_model.check_password
    verification = Barrier(2)

    def pause_success(self, raw_password):
        if raw_password == "right-password":
            verification.wait(10)
            verification.wait(10)
        return check_password(self, raw_password)

    monkeypatch.setattr(user_model, "check_password", pause_success)

    def attempt(password):
        try:
            response = Client().post(
                reverse("admin:login"),
                {"username": "owner", "password": password, "next": "/admin/"},
                HTTP_X_FORWARDED_FOR="192.168.178.50",
            )
            return response.status_code
        finally:
            connections.close_all()

    with override_settings(HOMELAB_LOGIN_FAILURE_LIMIT=LIMIT):
        assert attempt("wrong-password") == 200
        with ThreadPoolExecutor(max_workers=1) as pool:
            successful_login = pool.submit(attempt, "right-password")
            verification.wait(10)
            try:
                assert attempt("wrong-password") == 200
            finally:
                verification.wait(10)
            assert successful_login.result(timeout=10) == 302

    assert LoginThrottleBucket.objects.get(key__startswith="pair:").failures == 1
    assert sorted(LoginThrottleBucket.objects.exclude(key__startswith="pair:").values_list("failures", flat=True)) == [
        2,
        2,
    ]
