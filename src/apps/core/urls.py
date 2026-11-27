from django.urls import path

from .views import HomeView, connection_info, minecraft_power

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("connection-info/", connection_info, name="connection-info"),
    path("services/minecraft/power/", minecraft_power, name="minecraft-power"),
]
