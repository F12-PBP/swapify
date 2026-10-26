from django.utils.functional import cached_property
from django.views.generic import ListView, TemplateView

from apps.clothing_catalog.categories import DISCOVERY_TYPES
from apps.clothing_catalog.forms import DiscoveryFilterForm
from apps.clothing_catalog.selectors import discover_listings


class HomeView(TemplateView):
    template_name = "main/home.html"


class DiscoverView(ListView):
    template_name = "main/discover.html"
    context_object_name = "clothing_items"
    paginate_by = 12

    @cached_property
    def filter_form(self):
        form = DiscoveryFilterForm(self.request.GET)
        form.is_valid()
        return form

    def get_queryset(self):
        return discover_listings(self.request.user, self.filter_form.cleaned_data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        context["filters"] = self.filter_form.cleaned_data
        context["categories"] = DISCOVERY_TYPES
        return context


class SwapSafetyView(TemplateView):
    template_name = "main/safety.html"
