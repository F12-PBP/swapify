from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView
from django.views.generic.detail import SingleObjectMixin

from apps.clothing_catalog.models import Clothing

from .forms import SwapRequestForm
from .models import SwapRequest

RELATED_FIELDS = (
    "requester",
    "requested_clothing__owner",
    "offered_clothing",
)


class SwapRequestListView(LoginRequiredMixin, TemplateView):
    template_name = "swap_request/swap_request_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        swap_requests = SwapRequest.objects.select_related(*RELATED_FIELDS)
        user = self.request.user
        context["incoming_requests"] = swap_requests.filter(
            requested_clothing__owner=user
        )
        context["outgoing_requests"] = swap_requests.filter(requester=user)
        return context


class SwapRequestDetailView(LoginRequiredMixin, DetailView):
    context_object_name = "swap_request"
    template_name = "swap_request/swap_request_detail.html"

    def get_queryset(self):
        user = self.request.user
        return SwapRequest.objects.select_related(*RELATED_FIELDS).filter(
            Q(requester=user) | Q(requested_clothing__owner=user)
        )


class SwapRequestCreateView(LoginRequiredMixin, CreateView):
    form_class = SwapRequestForm
    template_name = "swap_request/swap_request_form.html"

    @cached_property
    def requested_clothing(self):
        other_available_clothing = (
            Clothing.objects.select_related("owner")
            .filter(availability=Clothing.Availability.AVAILABLE)
            .exclude(owner=self.request.user)
        )
        return get_object_or_404(
            other_available_clothing, pk=self.kwargs["clothing_pk"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["requester"] = self.request.user
        kwargs["requested_clothing"] = self.requested_clothing
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offerable_clothing = context["form"].fields["offered_clothing"].queryset
        context["requested_clothing"] = self.requested_clothing
        context["has_offerable_clothing"] = offerable_clothing.exists()
        return context

    def form_valid(self, form):
        messages.success(self.request, "Swap request berhasil dikirim.")
        return super().form_valid(form)


class SwapRequestActionView(LoginRequiredMixin, SingleObjectMixin, View):
    http_method_names = ["post"]
    new_status = None
    success_message = ""
    failure_message = "Swap request ini sudah tidak bisa diubah."

    def post(self, request, *args, **kwargs):
        swap_request = self.get_object()
        with transaction.atomic():
            if self.update_status(swap_request):
                messages.success(request, self.success_message)
            else:
                transaction.set_rollback(True)
                messages.error(request, self.failure_message)
        return redirect(swap_request)

    def update_status(self, swap_request):
        updated = SwapRequest.objects.filter(
            pk=swap_request.pk, status=SwapRequest.Status.PENDING
        ).update(status=self.new_status, updated_at=timezone.now())
        return updated == 1


class OwnerActionView(SwapRequestActionView):
    def get_queryset(self):
        return SwapRequest.objects.filter(requested_clothing__owner=self.request.user)


class SwapRequestAcceptView(OwnerActionView):
    new_status = SwapRequest.Status.ACCEPTED
    success_message = "Swap request diterima."
    failure_message = (
        "Swap request tidak bisa diterima karena sudah diproses "
        "atau salah satu pakaian sudah tidak tersedia."
    )

    def update_status(self, swap_request):
        reserved = Clothing.objects.filter(
            pk__in=[
                swap_request.requested_clothing_id,
                swap_request.offered_clothing_id,
            ],
            availability=Clothing.Availability.AVAILABLE,
        ).update(
            availability=Clothing.Availability.UNAVAILABLE,
            updated_at=timezone.now(),
        )
        return reserved == 2 and super().update_status(swap_request)


class SwapRequestRejectView(OwnerActionView):
    new_status = SwapRequest.Status.REJECTED
    success_message = "Swap request ditolak."


class SwapRequestCancelView(SwapRequestActionView):
    new_status = SwapRequest.Status.CANCELLED
    success_message = "Swap request dibatalkan."

    def get_queryset(self):
        return SwapRequest.objects.filter(requester=self.request.user)
