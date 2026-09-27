from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ClothingForm
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


class ClothingCreateView(LoginRequiredMixin, CreateView):
    form_class = ClothingForm
    template_name = "clothing_catalog/clothing_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.get_object().owner == self.request.user


class ClothingUpdateView(OwnerRequiredMixin, UpdateView):
    model = Clothing
    form_class = ClothingForm
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_form.html"


class ClothingDeleteView(OwnerRequiredMixin, DeleteView):
    model = Clothing
    context_object_name = "clothing"
    template_name = "clothing_catalog/clothing_confirm_delete.html"
    success_url = reverse_lazy("clothing_catalog:list")
