from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.cache import patch_vary_headers
from django.utils.functional import cached_property
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from common.redirects import safe_return_url

from .categories import DISCOVERY_TYPES
from .forms import ClothingForm, DiscoveryFilterForm
from .mixins import ClothingImageUploadMixin
from .models import Clothing
from .selectors import (
    catalog_search,
    discover_listings,
    listings_with_owners,
    related_listings,
    viewer_coordinates,
    with_distance,
)


class ClothingListView(ListView):
    template_name = "clothing_catalog/clothing_list.html"
    context_object_name = "clothing_items"
    paginate_by = 12

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Catalog-Request") == "results":
            response = JsonResponse(
                {
                    "html": render_to_string(
                        "clothing_catalog/partials/discovery_results.html",
                        context,
                        request=self.request,
                    ),
                    "filters": {
                        **self.filter_form.cleaned_data,
                        "sort": self.filter_form.cleaned_data.get("sort")
                        or "recommended",
                    },
                    "errors": self.filter_form.errors.get_json_data(),
                    "count": context["paginator"].count,
                }
            )
        else:
            response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Catalog-Request"])
        return response

    @cached_property
    def filter_form(self):
        form = DiscoveryFilterForm(
            self.request.GET, has_location=bool(viewer_coordinates(self.request.user))
        )
        form.is_valid()
        return form

    def get_queryset(self):
        return discover_listings(self.request.user, self.filter_form.cleaned_data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["filters"] = self.filter_form.cleaned_data
        context["categories"] = DISCOVERY_TYPES
        context["has_location"] = bool(viewer_coordinates(self.request.user))
        return context


class MyClothingListView(LoginRequiredMixin, ListView):
    model = Clothing
    context_object_name = "clothing_items"
    template_name = "clothing_catalog/wardrobe.html"
    paginate_by = 12

    def get_queryset(self):
        queryset = Clothing.objects.select_related("owner").filter(
            owner=self.request.user
        )

        # Search
        search = self.request.GET.get("search")
        queryset = catalog_search(queryset, search)

        # Filters
        clothing_type = self.request.GET.get("type")
        if clothing_type:
            queryset = queryset.filter(type=clothing_type)

        size = self.request.GET.get("size")
        if size:
            queryset = queryset.filter(size=size)

        condition = self.request.GET.get("condition")
        if condition:
            queryset = queryset.filter(condition=condition)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = Clothing.Type.choices
        context["sizes"] = Clothing.Size.choices
        context["conditions"] = Clothing.Condition.choices
        context["statuses"] = Clothing.Status.choices
        context["is_personal_view"] = True
        return context


class ClothingDetailView(DetailView):
    model = Clothing
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_detail.html"

    def get_queryset(self):
        return with_distance(listings_with_owners(), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_items"] = related_listings(self.request.user, self.object)
        return context


class ClothingCreateView(LoginRequiredMixin, ClothingImageUploadMixin, CreateView):
    form_class = ClothingForm
    template_name = "clothing_catalog/clothing_form.html"

    def get_success_url(self):
        return safe_return_url(self.request, super().get_success_url())

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Item added successfully.")
        return super().form_valid(form)


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return (
            obj.owner == self.request.user and obj.status == Clothing.Status.AVAILABLE
        )


class AvailableClothingMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "_lock_for_update", False):
            queryset = queryset.select_for_update(of=("self",))
        return queryset

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        self._lock_for_update = True
        return super().post(request, *args, **kwargs)


class ClothingUpdateView(
    OwnerRequiredMixin, AvailableClothingMixin, ClothingImageUploadMixin, UpdateView
):
    model = Clothing
    form_class = ClothingForm
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Item updated successfully.")
        return super().form_valid(form)


class ClothingDeleteView(OwnerRequiredMixin, AvailableClothingMixin, DeleteView):
    model = Clothing
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_confirm_delete.html"
    success_url = reverse_lazy("clothing_catalog:list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Item deleted successfully.")
        return super().delete(request, *args, **kwargs)
