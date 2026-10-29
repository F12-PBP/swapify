from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from django.views.generic.detail import SingleObjectMixin

from apps.clothing_catalog.models import Clothing

from .forms import SwapRequestFilterForm, SwapRequestForm
from .models import SwapRequest
from .services import (
    SwapAcceptanceError,
    SwapCreationError,
    accept_swap_request,
    create_swap_request,
)


def wants_fragment(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


class SwapRequestListView(LoginRequiredMixin, ListView):
    template_name = "swap_request/swap_request_list.html"
    results_template_name = "swap_request/partials/request_list.html"
    context_object_name = "swap_requests"
    paginate_by = 8

    @cached_property
    def filter_form(self):
        return SwapRequestFilterForm(self.request.GET)

    @cached_property
    def filters(self):
        return self.filter_form.values

    def get_queryset(self):
        user = self.request.user
        queryset = (
            SwapRequest.objects.for_user(user)
            .with_card_details(user)
            .search(self.filters["search"])
            .order_by("-created_at", "-pk")
        )
        if self.filters["role"] == "sent":
            queryset = queryset.filter(requester=user)
        elif self.filters["role"] == "received":
            queryset = queryset.filter(requested_clothing__owner=user)
        if self.filters["status"]:
            queryset = queryset.filter(status=self.filters["status"])
        return queryset

    def paginate_queryset(self, queryset, page_size):
        # Out-of-range pages fall back to the nearest page instead of a 404, so a
        # refresh after an item leaves the current page still shows results.
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get("page"))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        has_filters = any(self.filters.values())
        context["swap_filters"] = self.filters
        context["filter_form"] = self.filter_form
        context["has_filters"] = has_filters
        context["has_any_swaps"] = (
            has_filters
            or context["paginator"].count > 0
            or SwapRequest.objects.for_user(self.request.user).exists()
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Swap-Request") == "results":
            response = JsonResponse(
                {
                    "html": render_to_string(
                        self.results_template_name, context, request=self.request
                    ),
                    "filters": self.filters,
                    "page": context["page_obj"].number,
                    "count": context["paginator"].count,
                    "has_errors": bool(self.filter_form.errors),
                }
            )
        else:
            response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Swap-Request", "X-Requested-With"])
        return response


class SwapRequestDetailView(LoginRequiredMixin, DetailView):
    context_object_name = "swap_request"
    template_name = "swap_request/swap_request_detail.html"

    def get_queryset(self):
        user = self.request.user
        return SwapRequest.objects.for_user(user).with_card_details(user)

    def get_template_names(self):
        if wants_fragment(self.request):
            return ["swap_request/partials/swap_detail.html"]
        return super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Requested-With"])
        return response


class SwapRequestCreateView(LoginRequiredMixin, CreateView):
    form_class = SwapRequestForm
    template_name = "swap_request/swap_request_form.html"

    def get_template_names(self):
        if wants_fragment(self.request):
            return ["swap_request/partials/propose_form.html"]
        return super().get_template_names()

    @cached_property
    def requested_clothing(self):
        return get_object_or_404(
            Clothing.objects.select_related("owner__profile"),
            pk=self.kwargs["clothing_pk"],
        )

    @cached_property
    def unavailable_reason(self):
        if self.requested_clothing.owner_id == self.request.user.pk:
            return "own"
        if self.requested_clothing.status != Clothing.Status.AVAILABLE:
            return "unavailable"
        return ""

    @cached_property
    def previous_request(self):
        """A rejected or cancelled request being sent again from My swaps."""
        previous_pk = self.request.GET.get("from", "")
        if not previous_pk.isdigit():
            return None
        return (
            SwapRequest.objects.select_related("offered_clothing")
            .filter(
                pk=previous_pk,
                requester=self.request.user,
                requested_clothing=self.requested_clothing,
                status__in=(SwapRequest.Status.REJECTED, SwapRequest.Status.CANCELLED),
            )
            .first()
        )

    def get(self, request, *args, **kwargs):
        if self.unavailable_reason:
            return self.render_unavailable()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.unavailable_reason:
            return self.render_unavailable()
        return super().post(request, *args, **kwargs)

    def render_unavailable(self):
        self.object = None
        return self.render_to_response(
            {
                "requested_clothing": self.requested_clothing,
                "unavailable_reason": self.unavailable_reason,
            },
            status=409,
        )

    def get_initial(self):
        initial = super().get_initial()
        previous = self.previous_request
        # Resending a cancelled request keeps the same offer when it still can be.
        if (
            previous
            and previous.status == SwapRequest.Status.CANCELLED
            and previous.offered_clothing.status == Clothing.Status.AVAILABLE
        ):
            initial["offered_clothing"] = previous.offered_clothing_id
        return initial

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
        context["previous_request"] = self.previous_request
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
        if wants_fragment(self.request):
            return JsonResponse(
                {
                    "redirect": self.object.get_absolute_url(),
                    "html": render_to_string(
                        "swap_request/partials/request_sent.html",
                        {"swap_request": self.object},
                        request=self.request,
                    ),
                },
                status=201,
            )
        messages.success(self.request, "Your swap request has been sent.")
        return redirect(self.object)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if wants_fragment(self.request):
            response.status_code = 400
        return response


class SwapRequestActionView(LoginRequiredMixin, SingleObjectMixin, View):
    http_method_names = ["post"]
    new_status = None
    success_message = ""

    def post(self, request, *args, **kwargs):
        swap_request = self.get_object()
        with transaction.atomic():
            changed = self.update_status(swap_request)
            if not changed:
                transaction.set_rollback(True)
        message = (
            self.success_message if changed else self.failure_message(swap_request)
        )
        if wants_fragment(request):
            return JsonResponse({"message": message}, status=200 if changed else 409)
        if changed:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect(swap_request)

    def update_status(self, swap_request):
        updated = SwapRequest.objects.filter(
            pk=swap_request.pk, status=SwapRequest.Status.PENDING
        ).update(status=self.new_status, updated_at=timezone.now())
        return updated == 1

    def failure_message(self, swap_request):
        swap_request.refresh_from_db()
        if swap_request.status != SwapRequest.Status.PENDING:
            status = swap_request.get_status_display().lower()
            return f"This swap request was already {status}, so it can’t be changed."
        return "This swap request can’t be changed right now. Please try again."


class OwnerActionView(SwapRequestActionView):
    def get_queryset(self):
        return SwapRequest.objects.filter(requested_clothing__owner=self.request.user)


class SwapRequestAcceptView(OwnerActionView):
    new_status = SwapRequest.Status.ACCEPTED
    success_message = "Swap accepted. Say hello in Messages to plan the handover."

    def update_status(self, swap_request):
        try:
            accept_swap_request(
                request_id=swap_request.pk,
                acting_user=self.request.user,
            )
        except (SwapAcceptanceError, ValidationError):
            return False

        return True

    def failure_message(self, swap_request):
        message = super().failure_message(swap_request)
        blocking = swap_request.blocking_clothing
        if blocking:
            return (
                f"{blocking.name} is already part of another swap, "
                "so this request can’t be accepted."
            )
        return message


class SwapRequestRejectView(OwnerActionView):
    new_status = SwapRequest.Status.REJECTED
    success_message = "Swap request rejected. We’ll let them know."


class SwapRequestCancelView(SwapRequestActionView):
    new_status = SwapRequest.Status.CANCELLED
    success_message = "Swap request cancelled."

    def get_queryset(self):
        return SwapRequest.objects.filter(requester=self.request.user)
