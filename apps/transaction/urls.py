from django.urls import path

from . import views

urlpatterns = [
    path("<int:pk>/", views.TransactionDetailView.as_view(), name="transaction_detail"),
    path(
        "<int:pk>/update/",
        views.TransactionUpdateView.as_view(),
        name="transaction_update",
    ),
    path(
        "<int:pk>/received/",
        views.TransactionReceivedView.as_view(),
        name="transaction_received",
    ),
]
