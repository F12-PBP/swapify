from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    UpdateView,
)

from .forms import CreateTransactionForm, UpdateTransactionForm
from .models import Transaction


class CreateTransactionView(CreateView):
    model = Transaction
    form_class = CreateTransactionForm
    template_name = "transaction/create_transaction.html"

    def form_valid(self, form):
        transaction = form.save(commit=False)

        transaction.status = Transaction.Status.WAITING

        transaction.requester_resi_valid = False
        transaction.owner_resi_valid = False

        transaction.requester_received = False
        transaction.owner_received = False

        form.instance = transaction

        return super().form_valid(form)

    def get_success_url(self):
        return reverse("transaction_detail", kwargs={"pk": self.object.pk})


def delete_transaction_view(request, pk):
    if request.method == "POST":
        transaction = get_object_or_404(Transaction, pk=pk)
        transaction.delete()
    return redirect("transaction_base")


class TransactionDetailView(DetailView):
    model = Transaction
    template_name = "transaction/transaction_detail.html"
    context_object_name = "transaction"


class TransactionUpdateView(UpdateView):
    model = Transaction
    form_class = UpdateTransactionForm
    template_name = "transaction/transaction_update.html"
    context_object_name = "transaction"

    def get_success_url(self):
        return reverse("transaction_detail", kwargs={"pk": self.object.pk})


class TransactionReceivedView(View):
    def post(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk)

        party = request.POST.get("party")

        if party == "requester":
            transaction.requester_received = True

        elif party == "owner":
            transaction.owner_received = True

        else:
            return redirect("transaction_detail", pk=transaction.pk)

        transaction.save()

        return redirect("transaction_detail", pk=transaction.pk)
