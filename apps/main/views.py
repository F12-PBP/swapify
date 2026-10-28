from django.templatetags.static import static
from django.views.generic import TemplateView

from apps.clothing_catalog.selectors import discover_listings

STYLE_PIECES = (
    {
        "key": "shirt",
        "label": "Linen shirt",
        "name": "A lighter linen layer",
        "type": "top",
    },
    {
        "key": "jacket",
        "label": "Denim jacket",
        "name": "The everyday denim jacket",
        "type": "outerwear",
    },
    {"key": "knit", "label": "Cosy knit", "name": "A little more cosy", "type": "top"},
    {
        "key": "jeans",
        "label": "Blue jeans",
        "name": "Your next perfect fit",
        "type": "bottom",
    },
)


class HomeView(TemplateView):
    template_name = "main/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        featured = list(discover_listings(self.request.user)[:4])
        for clothing in featured:
            clothing.landing_illustration = {
                "top": "shirt",
                "outerwear": "jacket",
                "bottom": "jeans",
            }.get(clothing.type, "knit")
        context["featured_clothing"] = featured
        context["inspiration_pieces"] = STYLE_PIECES[len(featured) :]
        context["style_pieces"] = [
            {
                **piece,
                "image": static(f"images/landing_page/clothing/{piece['key']}.svg"),
            }
            for piece in STYLE_PIECES
        ]
        context["demo_choices"] = [
            (piece["key"], piece["label"]) for piece in STYLE_PIECES
        ]
        return context


class SwapSafetyView(TemplateView):
    template_name = "main/safety.html"
