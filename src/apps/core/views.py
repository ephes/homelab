from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView

from . import minecraft
from .client_addresses import canonical_ip, client_address, is_tailscale
from .models import Service

FORWARDED_FOR_PREVIEW_LENGTH = 256


class HomeView(ListView):
    """Homepage view showing all active services."""

    model = Service
    template_name = "core/home.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["minecraft_control_enabled"] = bool(settings.MINECRAFT_CONTROL_UNIT)
        return context


@csrf_exempt  # Apply CSRF protection after checking whether the endpoint is enabled.
def minecraft_power(request):
    if not settings.MINECRAFT_CONTROL_UNIT:
        raise Http404
    return _minecraft_power(request)


@csrf_protect
@never_cache
@require_http_methods(["GET", "POST"])
def _minecraft_power(request):
    if request.method == "GET":
        return JsonResponse(minecraft.status())

    action = request.POST.get("action")
    if action not in ("start", "stop"):
        return JsonResponse({"error": "Ungültige Aktion."}, status=400)

    if not minecraft.set_power(action):
        return JsonResponse({"error": "Minecraft-Befehl fehlgeschlagen."}, status=502)

    return JsonResponse({"state": "starting" if action == "start" else "stopping"}, status=202)


@never_cache
def connection_info(request):
    """Display connection information for debugging."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for and len(x_forwarded_for) > FORWARDED_FOR_PREVIEW_LENGTH:
        x_forwarded_for = "…" + x_forwarded_for[-(FORWARDED_FOR_PREVIEW_LENGTH - 1) :]
    client_ip = client_address(request, unknown="Unknown")
    ip = canonical_ip(client_ip)
    tailscale = ip is not None and is_tailscale(ip)

    context = {
        "client_ip": client_ip,
        "is_tailscale": tailscale,
        "is_local": ip is not None and not tailscale and ip.is_private,
        "server_hostname": request.get_host(),
        "request_host": request.META.get("HTTP_HOST", "Unknown"),
        "protocol": "HTTPS" if request.is_secure() else "HTTP",
        "forwarded_for": x_forwarded_for,
    }

    return render(request, "core/connection_info.html", context)
