"""
Tests for core app views.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.models import Service


@pytest.mark.django_db
class TestHomeView:
    """Test the home view."""

    def test_home_view_status_code(self, client):
        """Test that home view returns 200 status code."""
        url = reverse("core:home")
        response = client.get(url)
        assert response.status_code == 200

    def test_home_view_uses_correct_template(self, client):
        """Test that home view uses the correct template."""
        url = reverse("core:home")
        response = client.get(url)
        assert "core/home.html" in [t.name for t in response.templates]

    def test_home_view_displays_services(self, client, service):
        """Test that home view displays active services."""
        url = reverse("core:home")
        response = client.get(url)
        assert service.name in response.content.decode()
        assert service.description in response.content.decode()

    def test_home_view_filters_inactive_services(self, client, service):
        """Test that home view only shows active services."""
        # Make service inactive
        service.is_active = False
        service.save()

        url = reverse("core:home")
        response = client.get(url)
        assert service.name not in response.content.decode()

    def test_home_view_shows_no_services_message(self, client):
        """Test that home view shows message when no services exist."""
        url = reverse("core:home")
        response = client.get(url)
        assert "No services configured yet" in response.content.decode()

    def test_home_view_displays_service_with_logo(self, client):
        """Test that home view displays service with custom logo."""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        logo_file = SimpleUploadedFile("test_logo.svg", svg_content, content_type="image/svg+xml")

        service = Service.objects.create(
            name="Logo Service", description="Service with logo", logo_file=logo_file, is_active=True
        )

        url = reverse("core:home")
        response = client.get(url)
        content = response.content.decode()

        # Check that the service is displayed
        assert "Logo Service" in content
        assert "Service with logo" in content

        # Check that logo image tag is present
        assert '<img src="' in content
        assert 'alt="Logo Service logo"' in content
        assert 'class="service-logo"' in content

        # Clean up
        service.logo_file.delete()
        service.delete()

    def test_home_view_displays_service_with_icon_fallback(self, client):
        """Test that home view displays Font Awesome icon when no logo is present."""
        service = Service.objects.create(
            name="Icon Service", description="Service with icon", icon="fas fa-rocket", is_active=True
        )

        url = reverse("core:home")
        response = client.get(url)
        content = response.content.decode()

        # Check that the service is displayed
        assert "Icon Service" in content

        # Check that Font Awesome icon is used
        assert '<i class="fas fa-rocket"></i>' in content

        # No image tag should be present
        assert 'alt="Icon Service logo"' not in content

        service.delete()

    def test_home_view_displays_default_icon(self, client):
        """Test that home view displays default icon when no logo or icon is set."""
        service = Service.objects.create(
            name="Default Service", description="Service with default icon", is_active=True
        )

        url = reverse("core:home")
        response = client.get(url)
        content = response.content.decode()

        # Check that default server icon is used
        assert '<i class="fas fa-server"></i>' in content

        service.delete()


@pytest.fixture
def page_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "connection-info-test",
        }
    }
    settings.MIDDLEWARE = [
        "django.middleware.cache.UpdateCacheMiddleware",
        *settings.MIDDLEWARE,
        "django.middleware.cache.FetchFromCacheMiddleware",
    ]


@pytest.mark.django_db
class TestConnectionInfoView:
    """The connection-info page derives the client address from the proxy-appended XFF entry."""

    url = "/connection-info/"

    def get(self, client, xff=None, remote_addr="127.0.0.1"):
        extra = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return client.get(self.url, **extra)

    def test_connection_info_is_private_and_fresh_with_page_cache(self, client, page_cache):
        first = self.get(client, xff="192.0.2.10")
        second = self.get(client, xff="192.0.2.20")

        assert first.status_code == second.status_code == 200
        assert b"192.0.2.10" in first.content
        assert b"192.0.2.20" in second.content
        assert b"192.0.2.10" not in second.content
        for response in (first, second):
            directives = {part.strip() for part in response["Cache-Control"].split(",")}
            assert {"private", "no-store"} <= directives

        dashboard = client.get(reverse("core:home"))
        assert dashboard.status_code == 200
        assert "private" not in dashboard.get("Cache-Control", "")
        assert "no-store" not in dashboard.get("Cache-Control", "")

    def test_url_resolves(self):
        assert reverse("core:connection-info") == self.url

    def test_uses_rightmost_forwarded_entry(self, client):
        # A client-supplied Tailscale address on the left must not win over the proxy-appended one.
        response = self.get(client, xff="100.100.1.1, 8.8.4.4")
        assert response.status_code == 200
        assert response.context["client_ip"] == "8.8.4.4"
        assert response.context["is_tailscale"] is False
        assert response.context["is_local"] is False

    def test_spoofed_local_address_is_ignored(self, client):
        response = self.get(client, xff="192.168.178.10,8.8.4.4")
        assert response.context["client_ip"] == "8.8.4.4"
        assert response.context["is_local"] is False

    def test_tailscale_badge_from_proxy_entry(self, client):
        response = self.get(client, xff="100.119.21.5")
        assert response.context["client_ip"] == "100.119.21.5"
        assert response.context["is_tailscale"] is True

    @pytest.mark.parametrize(
        ("address", "is_tailscale", "is_local"),
        [
            ("fd7a:115c:a1e0::42", True, False),
            ("::ffff:100.100.1.42", True, False),
            ("fd50:3e45:c454::42", False, True),
        ],
    )
    def test_classifies_ipv6_and_mapped_addresses(self, client, address, is_tailscale, is_local):
        forwarded_for = f"192.0.2.10, {address}"
        response = self.get(client, xff=forwarded_for)

        assert response.status_code == 200
        assert response.context["is_tailscale"] is is_tailscale
        assert response.context["is_local"] is is_local
        assert response.context["forwarded_for"] == forwarded_for

    def test_local_badge_from_proxy_entry(self, client):
        response = self.get(client, xff="8.8.8.8, 192.168.178.20")
        assert response.context["is_local"] is True
        assert response.context["is_tailscale"] is False

    def test_ipv6_entry(self, client):
        response = self.get(client, xff="2001:db8::1")
        assert response.context["client_ip"] == "2001:db8::1"

    def test_falls_back_to_remote_addr_without_header(self, client):
        response = self.get(client, remote_addr="100.101.102.103")
        assert response.context["client_ip"] == "100.101.102.103"
        assert response.context["is_tailscale"] is True

    @pytest.mark.parametrize("xff", ["", " ", "1.2.3.4, ", "100.64.0.1, not-an-ip"])
    def test_falls_back_to_remote_addr_for_unusable_last_entry(self, client, xff):
        response = self.get(client, xff=xff, remote_addr="9.9.9.9")
        assert response.context["client_ip"] == "9.9.9.9"
        assert response.context["is_tailscale"] is False

    def test_raw_header_is_still_shown_for_debugging(self, client):
        response = self.get(client, xff="100.100.1.1, 8.8.4.4")
        assert response.context["forwarded_for"] == "100.100.1.1, 8.8.4.4"


def test_third_party_assets_are_pinned_by_subresource_integrity(client):
    """A compromised CDN must not be able to restyle pages or read the logout form's CSRF token."""
    from html.parser import HTMLParser

    class Assets(HTMLParser):
        def __init__(self):
            super().__init__()
            self.external = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            url = attrs.get("src") if tag == "script" else attrs.get("href") if tag == "link" else None
            if url and url.startswith(("https://", "http://", "//")):
                self.external.append(attrs)

    parser = Assets()
    parser.feed(client.get(reverse("core:home")).content.decode())

    assert parser.external, "the page is expected to load Font Awesome from the CDN"
    for attrs in parser.external:
        assert (attrs.get("integrity") or "").startswith(("sha384-", "sha512-")), attrs
        assert attrs.get("crossorigin") == "anonymous", attrs
        assert attrs.get("referrerpolicy") == "no-referrer", attrs
