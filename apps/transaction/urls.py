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
    path(
        "<uuid:pk>/cancel/",
        views.TransactionCancelView.as_view(),
        name="transaction_cancel",
    ),
    path(
        "<uuid:pk>/validate/",
        views.ResiValidatetView.as_view(),
        name="validate_resi",
    ),
    path(
        "<uuid:pk>/unvalidate/",
        views.ResiUnvalidatetView.as_view(),
        name="unvalidate_resi",
    ),
]
