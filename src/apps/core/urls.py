from django.urls import path

from .views import HomeView, connection_info

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("connection-info/", connection_info, name="connection-info"),
]
