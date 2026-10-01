from django.urls import path

from .views import (
    SwapRequestAcceptView,
    SwapRequestCancelView,
    SwapRequestCreateView,
    SwapRequestDetailView,
    SwapRequestListView,
    SwapRequestRejectView,
)

app_name = "swap_request"

urlpatterns = [
    path("", SwapRequestListView.as_view(), name="list"),
    path(
        "create/<int:clothing_pk>/",
        SwapRequestCreateView.as_view(),
        name="create",
    ),
    path("<int:pk>/", SwapRequestDetailView.as_view(), name="detail"),
    path("<int:pk>/accept/", SwapRequestAcceptView.as_view(), name="accept"),
    path("<int:pk>/reject/", SwapRequestRejectView.as_view(), name="reject"),
    path("<int:pk>/cancel/", SwapRequestCancelView.as_view(), name="cancel"),
]
