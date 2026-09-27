from django.test import TestCase
from django.urls import reverse


class DesignSystemViewTests(TestCase):
    def test_custom_dropdown_markup(self):
        response = self.client.get(reverse("design_system:ds"))

        self.assertContains(response, 'id="ds-dropdown"')
        self.assertContains(response, 'name="category" value=""')
        self.assertContains(response, "js/design-system-dropdown.js")

    def test_design_system_returns_ok(self):
        response = self.client.get(reverse("design_system:ds"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "design_system/ds.html")
        self.assertEqual(len(response.context["color_palettes"]), 6)
        self.assertEqual(
            sum(
                len(palette["swatches"])
                for palette in response.context["color_palettes"]
            ),
            64,
        )
        self.assertContains(response, "var(--color-primary-base)")
        self.assertContains(response, "var(--color-green-100)")
        self.assertContains(response, 'id="color-palette-title"', count=1)
        self.assertContains(response, "swap-chip")
        self.assertContains(response, "swap-alert-success")
        self.assertContains(response, "icons/alert-success.svg")
        self.assertContains(response, "icons/alert-close-success.svg")
        self.assertContains(response, 'id="ds-dropdown"')
        self.assertContains(response, 'data-value="choice-1"')
        self.assertContains(response, "js/design-system-dropdown.js")
        self.assertContains(response, 'name="ds-choice"')
        self.assertContains(response, "swap-accordion")
