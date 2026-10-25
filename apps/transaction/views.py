from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import (
    DetailView,
    UpdateView,
)

from apps.swap_request.models import SwapRequest

from .forms import UpdateTransactionForm
from .models import Transaction
from .services import confirm_receipt, start_transaction


class TransactionParticipantMixin(LoginRequiredMixin):
    def get_queryset(self):
        return Transaction.objects.select_related(
            "swap_request__requester",
            "swap_request__requested_clothing__owner",
        ).filter(
            Q(swap_request__requester=self.request.user)
            | Q(swap_request__requested_clothing__owner=self.request.user)
        )


class TransactionDetailView(TransactionParticipantMixin, DetailView):
    model = Transaction
    template_name = "transaction/transaction_detail.html"
    context_object_name = "transaction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exchange = self.object
        is_requester = self.request.user.pk == exchange.swap_request.requester_id
        context["my_received"] = (
            exchange.requester_received if is_requester else exchange.owner_received
        )
        context["has_reviewed"] = exchange.reviews.filter(
            author=self.request.user,
        ).exists()

        return context


class TransactionUpdateView(TransactionParticipantMixin, UpdateView):
    model = Transaction
    form_class = UpdateTransactionForm
    template_name = "transaction/transaction_update.html"
    context_object_name = "transaction"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method == "POST":
            queryset = queryset.select_for_update(of=("self",))
        return queryset

    def get_object(self, queryset=None):
        exchange = super().get_object(queryset)
        if (
            exchange.status != Transaction.Status.WAITING
            or exchange.swap_request.status != SwapRequest.Status.ACCEPTED
        ):
            raise PermissionDenied("Exchange details are locked after it starts.")
        return exchange

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("transaction_detail", kwargs={"pk": self.object.pk})


class TransactionStartView(TransactionParticipantMixin, View):
    def post(self, request, pk):
        exchange = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            start_transaction(exchange.pk, request.user)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
        else:
            messages.success(request, "Exchange started. Details are now locked.")
        return redirect("transaction_detail", pk=exchange.pk)


class TransactionReceivedView(TransactionParticipantMixin, View):
    def post(self, request, pk):
        exchange = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            exchange = confirm_receipt(exchange.pk, request.user)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
        else:
            if exchange.status == Transaction.Status.COMPLETED:
                messages.success(request, "Exchange completed. Both items are swapped.")
            else:
                messages.success(
                    request, "Receipt confirmed. Waiting for your partner."
                )

        return redirect("transaction_detail", pk=exchange.pk)
