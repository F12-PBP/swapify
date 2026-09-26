from django.shortcuts import render
from django.views import View

from .helpers import _use_light_text
from .static_data import COLOR_PALETTES


class DesignSystemView(View):
    def get(self, request):
        color_palettes = []

        for palette in COLOR_PALETTES:
            swatches = []

            for token, hex_color in palette["swatches"]:
                swatches.append(
                    {
                        "token": token,
                        "hex": hex_color,
                        "light_text": _use_light_text(hex_color),
                    }
                )

            color_palettes.append(
                {
                    "name": palette["name"],
                    "title": palette["title"],
                    "swatches": swatches,
                }
            )

        context = {"color_palettes": color_palettes}
        return render(request, "design_system/ds.html", context)
