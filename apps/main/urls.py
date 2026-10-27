from django.urls import path
from django.views.generic import RedirectView

from .views import HomeView, SwapSafetyView

app_name = "main"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path(
        "discover/",
        RedirectView.as_view(
            pattern_name="clothing_catalog:list", permanent=True, query_string=True
        ),
        name="legacy_discover",
    ),
    path("swap-safely/", SwapSafetyView.as_view(), name="safety"),
]
