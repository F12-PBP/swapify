from django.urls import path

from .api_views import (
    SwapRequestAcceptAPIView,
    SwapRequestCancelAPIView,
    SwapRequestDetailAPIView,
    SwapRequestListCreateAPIView,
    SwapRequestRejectAPIView,
)

app_name = "swap_request_api"

urlpatterns = [
    path(
        "swap-requests/",
        SwapRequestListCreateAPIView.as_view(),
        name="swap-request-list",
    ),
    path(
        "swap-requests/<int:pk>/",
        SwapRequestDetailAPIView.as_view(),
        name="swap-request-detail",
    ),
    path(
        "swap-requests/<int:pk>/accept/",
        SwapRequestAcceptAPIView.as_view(),
        name="swap-request-accept",
    ),
    path(
        "swap-requests/<int:pk>/reject/",
        SwapRequestRejectAPIView.as_view(),
        name="swap-request-reject",
    ),
    path(
        "swap-requests/<int:pk>/cancel/",
        SwapRequestCancelAPIView.as_view(),
        name="swap-request-cancel",
    ),
]
