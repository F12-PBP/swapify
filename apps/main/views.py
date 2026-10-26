from django.views.generic import ListView, TemplateView

from apps.clothing_catalog.selectors import discover_listings


class HomeView(TemplateView):
    template_name = "main/home.html"


class DiscoverView(ListView):
    template_name = "main/discover.html"
    context_object_name = "clothing_items"
    paginate_by = 12

    def get_queryset(self):
        return discover_listings(
            self.request.user, self.request.GET.get("search", "")[:150].strip()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = {"search": self.request.GET.get("search", "")[:150]}
        return context


class SwapSafetyView(TemplateView):
    template_name = "main/safety.html"
