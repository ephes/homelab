import ipaddress

from django.shortcuts import render
from django.views.generic import ListView

from .models import Service


class HomeView(ListView):
    """Homepage view showing all active services."""

    model = Service
    template_name = "core/home.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(is_active=True)


def client_ip_from_request(request):
    """Return the client address as seen by the reverse proxy in front of the app.

    Traefik appends the address it received the connection from to ``X-Forwarded-For``, so only the
    rightmost entry is trustworthy; anything to its left was sent by the client and can be spoofed.
    Falls back to ``REMOTE_ADDR`` when the header is missing or its last entry is not an IP address.
    Display only: never use this for access decisions.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = x_forwarded_for.split(",")[-1].strip()
    if candidate:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR") or "Unknown"


def connection_info(request):
    """Display connection information for debugging."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    client_ip = client_ip_from_request(request)

    # Check if it's a Tailscale IP (100.64.0.0/10)
    is_tailscale = False
    is_local = False
    try:
        ip = ipaddress.ip_address(client_ip)
        # Tailscale uses 100.64.0.0/10
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            is_tailscale = True
        # Check for local networks
        elif ip.is_private:
            is_local = True
    except ValueError:
        pass

    context = {
        "client_ip": client_ip,
        "is_tailscale": is_tailscale,
        "is_local": is_local,
        "server_hostname": request.get_host(),
        "request_host": request.META.get("HTTP_HOST", "Unknown"),
        "protocol": "HTTPS" if request.is_secure() else "HTTP",
        "forwarded_for": x_forwarded_for,
    }

    return render(request, "core/connection_info.html", context)
