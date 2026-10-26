from django.urls import path

from .views import DiscoverView, HomeView, SwapSafetyView

app_name = "main"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("discover/", DiscoverView.as_view(), name="discover"),
    path("swap-safely/", SwapSafetyView.as_view(), name="safety"),
]
