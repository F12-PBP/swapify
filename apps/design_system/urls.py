from django.urls import path

from .views import DesignSystemView

app_name = "design_system"

urlpatterns = [
    path("", DesignSystemView.as_view(), name="ds"),
]
