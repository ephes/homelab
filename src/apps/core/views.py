from django.views.generic import ListView

from .models import Service


class HomeView(ListView):
    """Homepage view showing all active services."""

    model = Service
    template_name = "core/home.html"
    context_object_name = "services"

    def get_queryset(self):
        return Service.objects.filter(is_active=True)
