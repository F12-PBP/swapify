from django.urls import path

from . import views

urlpatterns = [
    path("create/", views.CreateTransactionView.as_view(), name="create_transaction"),
    path("<int:pk>/", views.TransactionDetailView.as_view(), name="transaction_detail"),
    path("<int:pk>/delete/", views.delete_transaction_view, name="delete_transaction"),
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
