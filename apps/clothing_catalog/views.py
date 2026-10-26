from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ClothingForm
from .mixins import ClothingImageUploadMixin
from .models import Clothing


class ClothingListView(ListView):
    model = Clothing
    context_object_name = "clothing_items"
    template_name = "clothing_catalog/clothing_list.html"
    paginate_by = 12

    def get_queryset(self):
        queryset = Clothing.objects.select_related("owner")

        # Search
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

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
        return context


class MyClothingListView(LoginRequiredMixin, ClothingListView):
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_personal_view"] = True
        return context


class ClothingDetailView(DetailView):
    model = Clothing
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_detail.html"
    queryset = Clothing.objects.select_related("owner")


class ClothingCreateView(LoginRequiredMixin, ClothingImageUploadMixin, CreateView):
    form_class = ClothingForm
    template_name = "clothing_catalog/clothing_form.html"

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
