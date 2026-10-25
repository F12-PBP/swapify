from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
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
    queryset = Clothing.objects.select_related("owner")


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


class ClothingDeleteView(OwnerRequiredMixin, AvailableClothingMixin, DeleteView):
    model = Clothing
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_confirm_delete.html"
    success_url = reverse_lazy("clothing_catalog:list")
