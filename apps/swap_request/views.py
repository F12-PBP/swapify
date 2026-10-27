from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView
from django.views.generic.detail import SingleObjectMixin

from apps.clothing_catalog.models import Clothing

from .forms import SwapRequestForm
from .models import SwapRequest
from .services import (
    SwapAcceptanceError,
    SwapCreationError,
    accept_swap_request,
    create_swap_request,
)

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

    @property
    def wants_fragment(self):
        return self.request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def get_template_names(self):
        if self.wants_fragment:
            return ["swap_request/partials/propose_form.html"]
        return super().get_template_names()

    @cached_property
    def requested_clothing(self):
        other_available_clothing = (
            Clothing.objects.select_related("owner__profile")
            .filter(status=Clothing.Status.AVAILABLE)
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
        context["offered_choices"] = [
            choice for choice in context["form"].fields["offered_clothing"].choices
        ]
        context["requested_clothing"] = self.requested_clothing
        context["has_offerable_clothing"] = len(context["offered_choices"]) > 1
        return context

    def form_valid(self, form):
        try:
            self.object = create_swap_request(
                requester=self.request.user,
                requested_clothing_id=self.requested_clothing.pk,
                offered_clothing_id=form.cleaned_data["offered_clothing"].pk,
                message=form.cleaned_data["message"],
            )
        except SwapCreationError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, "Your swap request has been sent.")
        if self.wants_fragment:
            return JsonResponse(
                {"redirect": self.object.get_absolute_url()}, status=201
            )
        return redirect(self.object)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.wants_fragment:
            response.status_code = 400
        return response


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
        try:
            accept_swap_request(
                request_id=swap_request.pk,
                acting_user=self.request.user,
            )
        except (SwapAcceptanceError, ValidationError):
            return False

        return True


class SwapRequestRejectView(OwnerActionView):
    new_status = SwapRequest.Status.REJECTED
    success_message = "Swap request ditolak."


class SwapRequestCancelView(SwapRequestActionView):
    new_status = SwapRequest.Status.CANCELLED
    success_message = "Swap request dibatalkan."

    def get_queryset(self):
        return SwapRequest.objects.filter(requester=self.request.user)
