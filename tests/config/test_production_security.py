"""Production security settings: CSRF origins and the login throttle."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from .isolation import load_settings, make_project_root, settings_module_bootstrap

PRODUCTION_ENV = {
    "DJANGO_SECRET_KEY": "test-only-production-key",  # pragma: allowlist secret
    "DJANGO_ALLOWED_HOSTS": "127.0.0.1,home.xn--wersdrfer-47a.de",
}
HOST = "home.xn--wersdrfer-47a.de"


@pytest.fixture(scope="module")
def production(tmp_path_factory):
    root = make_project_root(tmp_path_factory.mktemp("production"))
    return load_settings(root, settings_module_bootstrap("config.settings.production"), PRODUCTION_ENV)


def test_production_trusts_no_extra_csrf_origins(production):
    # Same-origin POSTs never need a trusted origin. A wildcard would let any
    # sibling subdomain that tosses a csrftoken cookie forge admin requests.
    assert production["CSRF_TRUSTED_ORIGINS"] == []


def test_production_uses_the_login_throttle(production):
    assert production["AUTHENTICATION_BACKENDS"] == [
        "apps.core.login_throttle.LoginThrottleBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]


def csrf_login(origin):
    get_user_model().objects.create_superuser(username="owner", email="o@example.com", password="pw-123456789")
    client = Client(enforce_csrf_checks=True)
    token = "a" * 32  # a cookie value a sibling subdomain could have tossed
    client.cookies["csrftoken"] = token
    return client.post(
        reverse("admin:login"),
        {"username": "owner", "password": "pw-123456789", "csrfmiddlewaretoken": token},
        HTTP_HOST=HOST,
        HTTP_ORIGIN=origin,
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_X_FORWARDED_FOR="192.168.178.50",
    )


@pytest.mark.parametrize(
    ("origin", "status"),
    [(f"https://{HOST}", 302), (f"https://evil.{HOST}", 403), ("https://evil.home.wersdoerfer.de", 403)],
)
def test_production_csrf_origins_admit_only_the_site_itself(production, origin, status):
    with override_settings(
        CSRF_TRUSTED_ORIGINS=production["CSRF_TRUSTED_ORIGINS"],
        ALLOWED_HOSTS=[HOST],
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    ):
        assert csrf_login(origin).status_code == status
