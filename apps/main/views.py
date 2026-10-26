from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "main/home.html"


class DiscoverView(TemplateView):
    template_name = "main/discover.html"


class SwapSafetyView(TemplateView):
    template_name = "main/safety.html"
