from django.shortcuts import render
from django.views import View

from .helpers import _use_light_text
from .static_data import COLOR_PALETTES, TYPOGRAPHIES


class DesignSystemView(View):
    def get(self, request):
        color_palettes = []
        typographies = []

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

        for typography in TYPOGRAPHIES:
            styles = []

            for token, class_name, px, line_height in typography["styles"]:
                styles.append(
                    {
                        "token": token,
                        "class_name": class_name,
                        "px": px,
                        "line_height": line_height,
                    }
                )

            typographies.append(
                {
                    "name": typography["name"],
                    "title": typography["title"],
                    "font_class": typography["font_class"],
                    "styles": styles,
                }
            )

        context = {"color_palettes": color_palettes, "typographies": typographies}

        return render(request, "design_system/ds.html", context)
