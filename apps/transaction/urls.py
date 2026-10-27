from django.urls import path

from . import views

urlpatterns = [
    path(
        "<uuid:pk>/", views.TransactionDetailView.as_view(), name="transaction_detail"
    ),
    path(
        "<uuid:pk>/start/",
        views.TransactionStartView.as_view(),
        name="transaction_start",
    ),
    path(
        "<uuid:pk>/update/",
        views.TransactionUpdateView.as_view(),
        name="transaction_update",
    ),
    path(
        "<uuid:pk>/received/",
        views.TransactionReceivedView.as_view(),
        name="transaction_received",
    ),
]
