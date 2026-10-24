from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import (
    DetailView,
    UpdateView,
)

from .forms import UpdateTransactionForm
from .models import Transaction


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


class TransactionUpdateView(TransactionParticipantMixin, UpdateView):
    model = Transaction
    form_class = UpdateTransactionForm
    template_name = "transaction/transaction_update.html"
    context_object_name = "transaction"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("transaction_detail", kwargs={"pk": self.object.pk})


class TransactionReceivedView(TransactionParticipantMixin, View):
    def post(self, request, pk):
        transaction = get_object_or_404(self.get_queryset(), pk=pk)

        if request.user.pk == transaction.swap_request.requester_id:
            receipt_field = "requester_received"
        else:
            receipt_field = "owner_received"

        setattr(transaction, receipt_field, True)
        transaction.save(update_fields=[receipt_field])

        return redirect("transaction_detail", pk=transaction.pk)
