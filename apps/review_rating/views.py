from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.utils.functional import cached_property
from django.views.generic import FormView

from apps.transaction.models import Transaction

from .forms import ReviewForm
from .services import submit_review


class ReviewCreateView(LoginRequiredMixin, FormView):
    form_class = ReviewForm
    template_name = "review_rating/review_form.html"

    @property
    def dialog_mode(self):
        return self.request.headers.get("X-Review-Dialog") == "1"

    def get_template_names(self):
        if self.dialog_mode:
            return ["review_rating/partials/review_form.html"]
        return super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Review-Dialog"])
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.dialog_mode:
            response.status_code = 422
        return response

    @cached_property
    def exchange(self):
        queryset = Transaction.objects.select_related(
            "swap_request__requester",
            "swap_request__requested_clothing__owner",
        ).filter(
            Q(swap_request__requester=self.request.user)
            | Q(swap_request__requested_clothing__owner=self.request.user)
        )

        exchange = get_object_or_404(
            queryset,
            pk=self.kwargs["transaction_id"],
        )

        if exchange.status != Transaction.Status.COMPLETED:
            raise PermissionDenied("You can only review a completed transaction.")

        return exchange

    def get_form_kwargs(self):
        self.exchange
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transaction"] = self.exchange
        context["recipient"] = (
            self.exchange.owner
            if self.request.user.pk == self.exchange.requester.pk
            else self.exchange.requester
        )
        return context

    def form_valid(self, form):
        try:
            submit_review(
                transaction_id=self.exchange.pk,
                author=self.request.user,
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data["comment"],
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)
            return self.form_invalid(form)

        if self.dialog_mode:
            return JsonResponse({"message": "Your review has been submitted."})
        messages.success(self.request, "Your review has been submitted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "transaction_detail",
            kwargs={"pk": self.exchange.pk},
        )
