from django.urls import path

from .views import DesignSystemView, HomeView

app_name = "main"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("ds/", DesignSystemView.as_view(), name="ds"),
]
