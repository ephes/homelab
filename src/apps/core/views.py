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


def connection_info(request):
    """Display connection information for debugging."""
    # Get client IP
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.META.get("REMOTE_ADDR", "Unknown")

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
