from django.urls import path

from . import api_views

app_name = "transaction_api"

urlpatterns = [
    path(
        "<uuid:transaction_id>/",
        api_views.TransactionDetailAPIView.as_view(),
        name="transaction-detail",
    ),
    path(
        "<uuid:transaction_id>/update/",
        api_views.TransactionUpdateAPIView.as_view(),
        name="transaction-update",
    ),
    path(
        "<uuid:transaction_id>/start/",
        api_views.TransactionStartAPIView.as_view(),
        name="transaction-start",
    ),
    path(
        "<uuid:transaction_id>/cancel/",
        api_views.TransactionCancelAPIView.as_view(),
        name="transaction-cancel",
    ),
    path(
        "<uuid:transaction_id>/validate-resi/",
        api_views.TransactionValidateResiAPIView.as_view(),
        name="transaction-validate-resi",
    ),
    path(
        "<uuid:transaction_id>/unvalidate-resi/",
        api_views.TransactionUnvalidateResiAPIView.as_view(),
        name="transaction-unvalidate-resi",
    ),
    path(
        "<uuid:transaction_id>/confirm-received/",
        api_views.TransactionReceivedAPIView.as_view(),
        name="transaction-confirm-received",
    ),
]
